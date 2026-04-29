"""Celery worker configuration and tasks."""

import os

from celery import Celery
from celery.utils.log import get_task_logger

from src.core.settings import load_settings

settings = load_settings()

# Configure Celery
celery_app = Celery(
    "mongorag",
    broker=settings.redis_url,
    backend=settings.redis_url,
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
    autoretry_for=(ConnectionError, OSError),
    retry_backoff=10,
    retry_backoff_max=90,
)
def ingest_document(
    self,
    temp_path: str,
    document_id: str,
    tenant_id: str,
    title: str,
    source: str,
    metadata: dict | None = None,
) -> dict:
    """Process a document through the ingestion pipeline.

    This task runs synchronously inside the Celery worker. It uses
    asyncio.run() to execute the async pipeline methods.

    Args:
        temp_path: Path to the uploaded file in temp directory.
        document_id: MongoDB document ID (created by the endpoint).
        tenant_id: Tenant ID for isolation.
        title: Document title.
        source: Original filename.
        metadata: Optional metadata dict.

    Returns:
        Dict with document_id, status, chunk_count.
    """
    import asyncio

    async def _run() -> dict:
        from pymongo import AsyncMongoClient

        from src.models.document import DocumentModel, DocumentStatus
        from src.services.ingestion.chunker import ChunkingConfig, create_chunker
        from src.services.ingestion.embedder import create_embedder
        from src.services.ingestion.service import IngestionService

        client = AsyncMongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
        db = client[settings.mongodb_database]

        service = IngestionService(
            documents_collection=db[settings.mongodb_collection_documents],
            chunks_collection=db[settings.mongodb_collection_chunks],
        )

        try:
            # Update status to processing
            await service.update_status(document_id, tenant_id, DocumentStatus.PROCESSING)

            # Read and convert document
            from src.services.ingestion.ingest import DocumentIngestionPipeline, IngestionConfig

            config = IngestionConfig()
            pipeline = DocumentIngestionPipeline(config=config, tenant_id=tenant_id)
            content, docling_doc = pipeline.read_document(temp_path)

            if not content.strip():
                await service.update_status(
                    document_id,
                    tenant_id,
                    DocumentStatus.FAILED,
                    error_message="Document is empty or could not be parsed",
                )
                return {"document_id": document_id, "status": "failed", "chunk_count": 0}

            # Generate content hash
            content_hash = DocumentModel.hash_content(content)

            # Check for duplicate
            existing_doc = await service.check_duplicate(tenant_id, source, content_hash)
            if existing_doc:
                # Delete the new pending document — reuse existing
                await service.update_status(
                    document_id,
                    tenant_id,
                    DocumentStatus.FAILED,
                    error_message="Duplicate of existing document",
                )
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

            # Determine version
            latest_version = await service.get_latest_version(tenant_id, source)
            version = latest_version + 1

            # Extract title if not provided
            resolved_title = title if title else pipeline.extract_title(content, temp_path)

            # Chunk document
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
                return {"document_id": document_id, "status": "failed", "chunk_count": 0}

            # Embed chunks
            embedder = create_embedder()
            embedded_chunks = await embedder.embed_chunks(chunks)

            # Store chunks with tenant isolation
            chunk_count = await service.store_chunks(
                chunks=embedded_chunks,
                document_id=document_id,
                tenant_id=tenant_id,
                source=source,
                version=version,
                embedding_model=settings.embedding_model,
            )

            # Update document to ready
            await service.update_status(
                document_id,
                tenant_id,
                DocumentStatus.READY,
                chunk_count=chunk_count,
                content_hash=content_hash,
                version=version,
                content=content,
            )

            task_logger.info(
                "Ingestion complete: doc=%s, tenant=%s, chunks=%d",
                document_id,
                tenant_id,
                chunk_count,
            )

            return {
                "document_id": document_id,
                "status": "ready",
                "chunk_count": chunk_count,
            }

        except Exception as e:
            task_logger.exception("Ingestion failed: doc=%s, error=%s", document_id, str(e))
            # Sanitize error message — never persist raw exception strings
            # which may contain connection strings or API keys
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
            raise  # Let Celery retry if applicable

        finally:
            await client.close()
            # Clean up temp file and its UUID parent directory
            import shutil

            temp_dir = os.path.dirname(temp_path)
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
                task_logger.info("Cleaned up temp dir: %s", temp_dir)

    return asyncio.run(_run())


@celery_app.task(
    bind=True,
    name="mongorag.ingest_url",
    max_retries=2,
    autoretry_for=(ConnectionError,),
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
        import os
        import tempfile

        from pymongo import AsyncMongoClient

        from src.models.document import DocumentModel, DocumentStatus
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

        client = AsyncMongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
        db = client[settings.mongodb_database]
        service = IngestionService(
            documents_collection=db[settings.mongodb_collection_documents],
            chunks_collection=db[settings.mongodb_collection_chunks],
        )

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
                return {"document_id": document_id, "status": "failed", "chunk_count": 0}
            except URLFetchError as e:
                await service.update_status(
                    document_id,
                    tenant_id,
                    DocumentStatus.FAILED,
                    error_message=f"Fetch failed: {e}",
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
            temp_path = os.path.join(temp_dir, f"document{ext}")
            with open(temp_path, "wb") as f:
                f.write(fetched.content)

            config = IngestionConfig()
            pipeline = DocumentIngestionPipeline(config=config, tenant_id=tenant_id)

            content = ""
            docling_doc = None
            try:
                content, docling_doc = pipeline.read_document(temp_path)
            except Exception as docling_err:  # noqa: BLE001
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
                existing_id = str(existing_doc["_id"])
                return {
                    "document_id": existing_id,
                    "status": "ready",
                    "chunk_count": existing_doc.get("chunk_count", 0),
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

            task_logger.info(
                "URL ingestion complete: doc=%s tenant=%s url=%s chunks=%d",
                document_id,
                tenant_id,
                source,
                chunk_count,
            )
            return {
                "document_id": document_id,
                "status": "ready",
                "chunk_count": chunk_count,
            }

        except Exception as e:
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
            raise
        finally:
            await client.close()
            import shutil as _shutil

            if os.path.exists(temp_dir):
                _shutil.rmtree(temp_dir, ignore_errors=True)

    return asyncio.run(_run())
