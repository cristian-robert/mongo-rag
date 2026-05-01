"""Celery worker configuration and tasks."""

import os

from celery import Celery
from celery.utils.log import get_task_logger

from src.core.settings import load_settings
from src.services.blobstore import BlobAccessError

# Configure Celery. Each task re-reads settings via load_settings() inside
# `_run` so tests can monkeypatch env vars without also patching a
# module-level cache. The single import-time read below is only used for
# Celery's broker/backend wiring.
_settings_at_import = load_settings()
celery_app = Celery(
    "mongorag",
    broker=_settings_at_import.redis_url,
    backend=_settings_at_import.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

task_logger = get_task_logger(__name__)


@celery_app.task(
    bind=True,
    name="mongorag.ingest_document",
    max_retries=3,
    autoretry_for=(ConnectionError, OSError, BlobAccessError),
    retry_backoff=10,
    retry_backoff_max=90,
)
def ingest_document(
    self,
    blob_uri: str,
    document_id: str,
    tenant_id: str,
    title: str,
    source: str,
    metadata: dict | None = None,
) -> dict:
    """Process a document through the ingestion pipeline.

    Reads the blob via the configured BlobStore, streams it to a tempfile,
    runs the existing pipeline, deletes the blob on success/terminal failure.

    Args:
        blob_uri: BlobStore URI (file://... or supabase://...). Must be tenant-prefixed.
        document_id: MongoDB document ID (created by the endpoint).
        tenant_id: Tenant ID for isolation; verified against the blob URI prefix.
        title: Document title.
        source: Original filename.
        metadata: Optional metadata dict.
    """
    import asyncio

    async def _run() -> dict:
        import tempfile

        from pymongo import AsyncMongoClient

        from src.models.document import DocumentModel, DocumentStatus
        from src.services.blobstore import (
            BlobAccessError,
            BlobNotFoundError,
            assert_tenant_owns_uri,
            extract_extension,
            get_blob_store,
        )
        from src.services.ingestion.chunker import ChunkingConfig, create_chunker
        from src.services.ingestion.embedder import create_embedder
        from src.services.ingestion.ingest import (
            DocumentIngestionPipeline,
            IngestionConfig,
        )
        from src.services.ingestion.service import IngestionService

        settings = load_settings()

        # Security boundary: verify tenant ownership BEFORE any read.
        assert_tenant_owns_uri(blob_uri, tenant_id)

        client = AsyncMongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
        db = client[settings.mongodb_database]

        service = IngestionService(
            documents_collection=db[settings.mongodb_collection_documents],
            chunks_collection=db[settings.mongodb_collection_chunks],
        )

        blob_store = get_blob_store()
        blob_size = 0
        blob_read_failed = False
        docling_failed = False
        tmp_path: str | None = None
        committed = False  # True after update_status(READY) lands
        chunk_count: int = 0

        try:
            await service.update_status(document_id, tenant_id, DocumentStatus.PROCESSING)

            ext = extract_extension(blob_uri) or ".bin"

            # Stream blob → tempfile (Docling needs a real path).
            try:
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as dst:
                    tmp_path = dst.name
                    async with blob_store.open(blob_uri) as stream:
                        async for chunk in stream:
                            dst.write(chunk)
                            blob_size += len(chunk)
            except BlobNotFoundError as e:
                blob_read_failed = True
                await service.update_status(
                    document_id,
                    tenant_id,
                    DocumentStatus.FAILED,
                    error_message=f"blob_not_found: {e}",
                )
                # Terminal — delete the (already-missing) blob and surface as success-no-retry.
                await _safe_delete(blob_store, blob_uri)
                return {"document_id": document_id, "status": "failed", "chunk_count": 0}
            except BlobAccessError:
                blob_read_failed = True
                # Retryable — autoretry_for catches this and Celery schedules a retry.
                raise

            # Existing pipeline.
            config = IngestionConfig()
            pipeline = DocumentIngestionPipeline(
                config=config, tenant_id=tenant_id, clean_before_ingest=False
            )

            try:
                content, docling_doc = pipeline.read_document(tmp_path)
            except Exception:
                docling_failed = True
                raise

            if not content.strip():
                await service.update_status(
                    document_id,
                    tenant_id,
                    DocumentStatus.FAILED,
                    error_message="Document is empty or could not be parsed",
                )
                await _safe_delete(blob_store, blob_uri)
                return {"document_id": document_id, "status": "failed", "chunk_count": 0}

            content_hash = DocumentModel.hash_content(content)

            existing_doc = await service.check_duplicate(tenant_id, source, content_hash)
            if existing_doc:
                await service.update_status(
                    document_id,
                    tenant_id,
                    DocumentStatus.FAILED,
                    error_message="Duplicate of existing document",
                )
                await _safe_delete(blob_store, blob_uri)
                existing_id = str(existing_doc["_id"])
                existing_chunks = existing_doc.get("chunk_count", 0)
                task_logger.info(
                    "Duplicate detected for %s, reusing existing %s",
                    document_id,
                    existing_id,
                )
                return {
                    "document_id": existing_id,
                    "status": "ready",
                    "chunk_count": existing_chunks,
                }

            latest_version = await service.get_latest_version(tenant_id, source)
            version = latest_version + 1
            resolved_title = title if title else pipeline.extract_title(content, tmp_path)

            chunker = create_chunker(ChunkingConfig(max_tokens=config.max_tokens))
            chunks = await chunker.chunk_document(
                content=content,
                title=resolved_title,
                source=source,
                metadata=metadata or {},
                docling_doc=docling_doc,
            )

            if not chunks:
                await service.update_status(
                    document_id,
                    tenant_id,
                    DocumentStatus.FAILED,
                    error_message="No chunks created from document",
                )
                await _safe_delete(blob_store, blob_uri)
                return {"document_id": document_id, "status": "failed", "chunk_count": 0}

            embedder = create_embedder()
            embedded_chunks = await embedder.embed_chunks(chunks)

            chunk_count = await service.store_chunks(
                chunks=embedded_chunks,
                document_id=document_id,
                tenant_id=tenant_id,
                source=source,
                version=version,
                embedding_model=settings.embedding_model,
            )

            await service.update_status(
                document_id,
                tenant_id,
                DocumentStatus.READY,
                chunk_count=chunk_count,
                content_hash=content_hash,
                version=version,
                content=content,
            )
            committed = True

            # Success — delete blob (lifecycle rule is the safety net if this fails).
            await _safe_delete(blob_store, blob_uri)

            _emit_ingestion_complete(
                document_id=document_id,
                tenant_id=tenant_id,
                blob_uri=blob_uri,
                blob_size_bytes=blob_size,
                status="ready",
                chunks=chunk_count,
                blob_read_failed=False,
                docling_failed=False,
                source_kind="upload",
            )

            return {
                "document_id": document_id,
                "status": "ready",
                "chunk_count": chunk_count,
            }

        except Exception as e:
            if committed:
                # Post-success exception (delete or log raised). The doc was
                # already persisted READY — do NOT mark it FAILED. The lifecycle
                # rule will catch any leaked blob.
                task_logger.warning(
                    "post_success_exception",
                    extra={
                        "document_id": document_id,
                        "tenant_id": tenant_id,
                        "exc": type(e).__name__,
                        "msg": str(e)[:200],
                    },
                )
                return {
                    "document_id": document_id,
                    "status": "ready",
                    "chunk_count": chunk_count,
                }

            # Retryable + retries remaining: Celery autoretry will pick this up.
            # Do NOT flip the doc to FAILED, do NOT delete the blob, do NOT
            # emit ingestion_complete — otherwise the dashboard sees a
            # transient FAILED → READY flap when the retry succeeds.
            if _will_celery_retry(self, e):
                task_logger.warning(
                    "retryable_exception_letting_celery_retry",
                    extra={
                        "document_id": document_id,
                        "tenant_id": tenant_id,
                        "exc": type(e).__name__,
                        "retries": self.request.retries,
                        "max_retries": self.max_retries,
                    },
                )
                raise

            task_logger.exception("Ingestion failed: doc=%s, error=%s", document_id, str(e))
            safe_error = type(e).__name__
            if isinstance(e, (ValueError, TypeError, FileNotFoundError)):
                safe_error = f"{type(e).__name__}: {str(e)}"
            try:
                await service.update_status(
                    document_id,
                    tenant_id,
                    DocumentStatus.FAILED,
                    error_message=safe_error,
                )
            except Exception:
                task_logger.exception("Failed to update status after error")

            _emit_ingestion_complete(
                document_id=document_id,
                tenant_id=tenant_id,
                blob_uri=blob_uri,
                blob_size_bytes=blob_size,
                status="failed",
                chunks=0,
                blob_read_failed=blob_read_failed,
                docling_failed=docling_failed,
                source_kind="upload",
            )

            # Terminal-after-retries cleanup (helper at module level).
            if _is_terminal_failure(self, e):
                await _safe_delete(blob_store, blob_uri)

            raise

        finally:
            await client.close()
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    return asyncio.run(_run())


@celery_app.task(
    bind=True,
    name="mongorag.ingest_url",
    max_retries=2,
    autoretry_for=(ConnectionError, BlobAccessError),
    retry_backoff=15,
    retry_backoff_max=120,
)
def ingest_url(
    self,
    url: str,
    document_id: str,
    tenant_id: str,
    title: str | None = None,
    metadata: dict | None = None,
) -> dict:
    """Fetch a URL, convert it to markdown, and run the full ingestion pipeline.

    SSRF defense and size/MIME limits live in
    :mod:`src.services.ingestion.url_loader`. This task is the same
    chunk → embed → persist flow as :func:`ingest_document`, but the source is
    the fetched response body written to a temp file so Docling sees a real
    path with the right extension.

    Args:
        url: User-supplied URL to fetch.
        document_id: Pre-created document ID.
        tenant_id: Tenant ID for isolation.
        title: Optional caller-supplied title override.
        metadata: Optional caller metadata.
    """
    import asyncio

    async def _run() -> dict:
        import io
        import os
        import tempfile

        from pymongo import AsyncMongoClient

        from src.models.document import DocumentModel, DocumentStatus
        from src.services.blobstore import get_blob_store
        from src.services.ingestion.chunker import ChunkingConfig, create_chunker
        from src.services.ingestion.embedder import create_embedder
        from src.services.ingestion.ingest import DocumentIngestionPipeline, IngestionConfig
        from src.services.ingestion.service import IngestionService
        from src.services.ingestion.url_loader import (
            URLFetchError,
            URLValidationError,
            fetch_url,
            html_to_markdown,
        )

        settings = load_settings()

        client = AsyncMongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
        db = client[settings.mongodb_database]
        service = IngestionService(
            documents_collection=db[settings.mongodb_collection_documents],
            chunks_collection=db[settings.mongodb_collection_chunks],
        )

        blob_uri: str | None = None
        blob_store = None
        blob_size: int = 0
        docling_failed = False
        committed = False  # True after update_status(READY) lands
        chunk_count: int = 0
        temp_dir = tempfile.mkdtemp(prefix="mongorag-url-")
        try:
            await service.update_status(document_id, tenant_id, DocumentStatus.PROCESSING)

            try:
                fetched = await fetch_url(url, settings)
            except URLValidationError as e:
                await service.update_status(
                    document_id,
                    tenant_id,
                    DocumentStatus.FAILED,
                    error_message=f"URL rejected: {e}",
                )
                _emit_ingestion_complete(
                    document_id=document_id,
                    tenant_id=tenant_id,
                    blob_uri=None,
                    blob_size_bytes=0,
                    status="failed",
                    chunks=0,
                    blob_read_failed=False,
                    docling_failed=False,
                    source_kind="url",
                )
                return {"document_id": document_id, "status": "failed", "chunk_count": 0}
            except URLFetchError as e:
                await service.update_status(
                    document_id,
                    tenant_id,
                    DocumentStatus.FAILED,
                    error_message=f"Fetch failed: {e}",
                )
                # No blob exists yet — fetch failed before put(). blob_read_failed
                # specifically signals a BlobStore read failure and would skew
                # ops dashboards if reused for upstream URL-fetch failures.
                _emit_ingestion_complete(
                    document_id=document_id,
                    tenant_id=tenant_id,
                    blob_uri=None,
                    blob_size_bytes=0,
                    status="failed",
                    chunks=0,
                    blob_read_failed=False,
                    docling_failed=False,
                    source_kind="url",
                )
                return {"document_id": document_id, "status": "failed", "chunk_count": 0}

            # Pick an extension based on detected MIME so Docling routes correctly.
            _docx = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            _pptx = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            _xlsx = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            mime_to_ext = {
                "text/html": ".html",
                "application/xhtml+xml": ".html",
                "text/plain": ".txt",
                "text/markdown": ".md",
                "application/pdf": ".pdf",
                "application/msword": ".doc",
                _docx: ".docx",
                "application/vnd.ms-powerpoint": ".ppt",
                _pptx: ".pptx",
                "application/vnd.ms-excel": ".xls",
                _xlsx: ".xlsx",
            }
            ext = mime_to_ext.get(fetched.content_type, ".bin")
            blob_store = get_blob_store()
            key = f"{tenant_id}/{document_id}/url-fetch{ext}"
            blob_uri = await blob_store.put(key, io.BytesIO(fetched.content), fetched.content_type)
            blob_size = len(fetched.content)

            # Stream back to a tempfile in the worker — same hot path as ingest_document.
            temp_path = os.path.join(temp_dir, f"document{ext}")
            async with blob_store.open(blob_uri) as stream:
                with open(temp_path, "wb") as f:
                    async for chunk in stream:
                        f.write(chunk)

            config = IngestionConfig()
            pipeline = DocumentIngestionPipeline(config=config, tenant_id=tenant_id)

            content = ""
            docling_doc = None
            try:
                content, docling_doc = pipeline.read_document(temp_path)
            except Exception as docling_err:  # noqa: BLE001
                docling_failed = True
                task_logger.warning(
                    "Docling failed for URL ingestion (doc=%s): %s — falling back",
                    document_id,
                    docling_err,
                )

            # Fallback: pure-Python HTML→markdown if Docling produced nothing useful.
            if (not content or not content.strip()) and fetched.content_type in {
                "text/html",
                "application/xhtml+xml",
            }:
                content = html_to_markdown(fetched.content, fetched.charset)

            if not content or not content.strip():
                await service.update_status(
                    document_id,
                    tenant_id,
                    DocumentStatus.FAILED,
                    error_message="Could not extract text from URL",
                )
                if blob_store is not None and blob_uri is not None:
                    await _safe_delete(blob_store, blob_uri)
                _emit_ingestion_complete(
                    document_id=document_id,
                    tenant_id=tenant_id,
                    blob_uri=blob_uri,
                    blob_size_bytes=blob_size,
                    status="failed",
                    chunks=0,
                    blob_read_failed=False,
                    docling_failed=docling_failed,
                    source_kind="url",
                )
                return {"document_id": document_id, "status": "failed", "chunk_count": 0}

            content_hash = DocumentModel.hash_content(content)
            source = fetched.final_url

            existing_doc = await service.check_duplicate(tenant_id, source, content_hash)
            if existing_doc:
                await service.update_status(
                    document_id,
                    tenant_id,
                    DocumentStatus.FAILED,
                    error_message="Duplicate of existing document",
                )
                if blob_store is not None and blob_uri is not None:
                    await _safe_delete(blob_store, blob_uri)
                existing_id = str(existing_doc["_id"])
                existing_chunks = existing_doc.get("chunk_count", 0)
                _emit_ingestion_complete(
                    document_id=existing_id,
                    tenant_id=tenant_id,
                    blob_uri=blob_uri,
                    blob_size_bytes=blob_size,
                    status="ready",
                    chunks=existing_chunks,
                    blob_read_failed=False,
                    docling_failed=docling_failed,
                    source_kind="url",
                )
                return {
                    "document_id": existing_id,
                    "status": "ready",
                    "chunk_count": existing_chunks,
                }

            latest_version = await service.get_latest_version(tenant_id, source)
            version = latest_version + 1

            resolved_title = title if title else pipeline.extract_title(content, temp_path)

            chunker = create_chunker(ChunkingConfig(max_tokens=config.max_tokens))
            merged_meta = dict(metadata or {})
            merged_meta.update(
                {
                    "source_url": fetched.url,
                    "final_url": fetched.final_url,
                    "content_type": fetched.content_type,
                }
            )
            chunks = await chunker.chunk_document(
                content=content,
                title=resolved_title,
                source=source,
                metadata=merged_meta,
                docling_doc=docling_doc,
            )

            if not chunks:
                await service.update_status(
                    document_id,
                    tenant_id,
                    DocumentStatus.FAILED,
                    error_message="No chunks created from URL",
                )
                if blob_store is not None and blob_uri is not None:
                    await _safe_delete(blob_store, blob_uri)
                _emit_ingestion_complete(
                    document_id=document_id,
                    tenant_id=tenant_id,
                    blob_uri=blob_uri,
                    blob_size_bytes=blob_size,
                    status="failed",
                    chunks=0,
                    blob_read_failed=False,
                    docling_failed=docling_failed,
                    source_kind="url",
                )
                return {"document_id": document_id, "status": "failed", "chunk_count": 0}

            embedder = create_embedder()
            embedded_chunks = await embedder.embed_chunks(chunks)

            chunk_count = await service.store_chunks(
                chunks=embedded_chunks,
                document_id=document_id,
                tenant_id=tenant_id,
                source=source,
                version=version,
                embedding_model=settings.embedding_model,
            )

            await service.update_status(
                document_id,
                tenant_id,
                DocumentStatus.READY,
                chunk_count=chunk_count,
                content_hash=content_hash,
                version=version,
                content=content,
            )
            committed = True

            # Success — delete blob (lifecycle rule is the safety net if this fails).
            await _safe_delete(blob_store, blob_uri)

            _emit_ingestion_complete(
                document_id=document_id,
                tenant_id=tenant_id,
                blob_uri=blob_uri,
                blob_size_bytes=blob_size,
                status="ready",
                chunks=chunk_count,
                blob_read_failed=False,
                docling_failed=docling_failed,
                source_kind="url",
            )
            return {
                "document_id": document_id,
                "status": "ready",
                "chunk_count": chunk_count,
            }

        except Exception as e:
            if committed:
                # Post-success exception (delete or log raised). The doc was
                # already persisted READY — do NOT mark it FAILED. The lifecycle
                # rule will catch any leaked blob.
                task_logger.warning(
                    "post_success_exception",
                    extra={
                        "document_id": document_id,
                        "tenant_id": tenant_id,
                        "exc": type(e).__name__,
                        "msg": str(e)[:200],
                    },
                )
                return {
                    "document_id": document_id,
                    "status": "ready",
                    "chunk_count": chunk_count,
                }

            # Retryable + retries remaining: Celery autoretry will pick this up.
            # Keep the blob (retry can re-stream instead of re-fetching), keep
            # the doc in PROCESSING, and skip the ingestion_complete emit so
            # dashboards don't see a transient FAILED → READY flap.
            if _will_celery_retry(self, e):
                task_logger.warning(
                    "retryable_exception_letting_celery_retry",
                    extra={
                        "document_id": document_id,
                        "tenant_id": tenant_id,
                        "exc": type(e).__name__,
                        "retries": self.request.retries,
                        "max_retries": self.max_retries,
                    },
                )
                raise

            task_logger.exception("URL ingestion failed: doc=%s err=%s", document_id, e)
            safe_error = type(e).__name__
            try:
                await service.update_status(
                    document_id,
                    tenant_id,
                    DocumentStatus.FAILED,
                    error_message=safe_error,
                )
            except Exception:
                task_logger.exception("Failed to update status after error")

            _emit_ingestion_complete(
                document_id=document_id,
                tenant_id=tenant_id,
                blob_uri=blob_uri,
                blob_size_bytes=blob_size,
                status="failed",
                chunks=0,
                blob_read_failed=False,
                docling_failed=docling_failed,
                source_kind="url",
            )

            # Terminal-after-retries cleanup. Transient retryable errors keep the
            # blob so the retry can re-stream from it instead of re-fetching the URL.
            if blob_store is not None and blob_uri is not None and _is_terminal_failure(self, e):
                await _safe_delete(blob_store, blob_uri)
            raise
        finally:
            await client.close()
            import shutil as _shutil

            if os.path.exists(temp_dir):
                _shutil.rmtree(temp_dir, ignore_errors=True)

    return asyncio.run(_run())


async def _safe_delete(blob_store, blob_uri: str) -> None:
    """Delete with logged-but-swallowed BlobStoreError. ValueError propagates."""
    from src.services.blobstore import BlobStoreError

    try:
        await blob_store.delete(blob_uri)
    except BlobStoreError as e:
        task_logger.warning("blob_delete_failed: uri=%s err=%s", blob_uri, e)
    # Programming errors (ValueError from URI parsing, AttributeError, etc.)
    # propagate — they indicate a bug, not a transient infra issue.


def _emit_ingestion_complete(
    *,
    document_id: str,
    tenant_id: str,
    blob_uri: str | None,
    blob_size_bytes: int,
    status: str,
    chunks: int,
    blob_read_failed: bool,
    docling_failed: bool,
    source_kind: str,  # "upload" or "url"
) -> None:
    """Single shape for the structured ingestion-outcome log line."""
    task_logger.info(
        "ingestion_complete",
        extra={
            "document_id": document_id,
            "tenant_id": tenant_id,
            "blob_uri": blob_uri,
            "blob_size_bytes": blob_size_bytes,
            "status": status,
            "chunks": chunks,
            "blob_read_failed": blob_read_failed,
            "docling_failed": docling_failed,
            "source_kind": source_kind,
        },
    )


def _is_terminal_failure(task, exc: Exception) -> bool:
    """Returns True if this is the last attempt (no more retries) or a non-retryable exc."""
    from src.services.blobstore import BlobNotFoundError, TenantOwnershipError

    if isinstance(exc, (BlobNotFoundError, TenantOwnershipError, ValueError, TypeError)):
        return True
    return task.request.retries >= task.max_retries


def _will_celery_retry(task, exc: Exception) -> bool:
    """True iff Celery's ``autoretry_for`` will pick up this exception and retries remain.

    Used to decide whether to mutate doc state on the way out of the worker:
    if Celery is going to retry, we must NOT flip the doc to FAILED — otherwise
    the dashboard sees a transient FAILED → READY flap on the retry.
    """
    autoretry_for = getattr(task, "autoretry_for", ()) or ()
    if not isinstance(exc, tuple(autoretry_for)):
        return False
    return task.request.retries < task.max_retries
