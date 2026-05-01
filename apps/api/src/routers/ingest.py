"""Document ingestion endpoints."""

import json
import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from src.core.dependencies import AgentDependencies
from src.core.deps import get_deps
from src.core.rate_limit_dep import enforce_rate_limit
from src.core.settings import Settings, load_settings
from src.core.tenant import get_tenant_id
from src.models.api import DocumentStatusResponse, IngestResponse, IngestURLRequest
from src.models.usage import QuotaExceededError
from src.services.ingestion.service import IngestionService
from src.services.ingestion.url_loader import URLValidationError, validate_url
from src.services.usage import UsageService
from src.worker import ingest_document, ingest_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".md",
    ".markdown",
    ".docx",
    ".doc",
    ".pptx",
    ".ppt",
    ".xlsx",
    ".xls",
    ".html",
    ".htm",
}


class _UploadTooLargeError(Exception):
    """Raised by _SizeCappedReader when bytes read exceed the configured cap."""


class _SizeCappedReader:
    """Wraps a BinaryIO to enforce a hard byte cap during streaming reads.

    UploadFile.size is unreliable for streamed multipart uploads (often None
    until the body is fully consumed), so a content-length pre-check leaves
    the BlobStore exposed to unbounded streams. This adapter counts bytes as
    the BlobStore reads them and raises :class:`_UploadTooLargeError` the
    moment the cap is exceeded — the BlobStore's own ``put`` exception
    handling cleans up any partial blob, so the only thing the router has
    to do on catch is return 413.
    """

    def __init__(self, src, max_bytes: int) -> None:
        self._src = src
        self._max = max_bytes
        self._read = 0

    def read(self, size: int = -1) -> bytes:
        chunk = self._src.read(size)
        self._read += len(chunk)
        if self._read > self._max:
            raise _UploadTooLargeError(
                f"upload exceeded cap of {self._max} bytes (read={self._read})"
            )
        return chunk


def _get_settings() -> Settings:
    return load_settings()


def _validate_file(file: UploadFile, settings: Settings) -> str:
    """Validate uploaded file format and size.

    Args:
        file: Uploaded file.
        settings: App settings for size limits.

    Returns:
        File extension string.

    Raises:
        HTTPException: 422 for unsupported format, 413 for oversized file.
    """
    filename = file.filename or "unknown"
    ext = os.path.splitext(filename)[1].lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unsupported file format: {ext}. "
                f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            ),
        )

    if file.size and file.size > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {settings.max_upload_size_mb}MB",
        )

    return ext


@router.post("/ingest", response_model=IngestResponse, status_code=202)
async def ingest_document_endpoint(
    file: UploadFile = File(...),
    title: Optional[str] = Form(default=None),
    metadata: Optional[str] = Form(default=None),
    tenant_id: str = Depends(enforce_rate_limit),
    settings: Settings = Depends(_get_settings),
    deps: AgentDependencies = Depends(get_deps),
) -> IngestResponse:
    """Upload and ingest a document.

    Validates the file, creates a pending document record, saves the file
    to a temp directory, and dispatches a Celery task for processing.

    Returns 202 Accepted immediately with document_id and task_id.
    """
    ext = _validate_file(file, settings)

    # Enforce documents-max quota before accepting the upload.
    usage_service = UsageService(deps.usage_collection, deps.subscriptions_collection)
    current_doc_count = await deps.documents_collection.count_documents({"tenant_id": tenant_id})
    try:
        await usage_service.check_document_quota(tenant_id, current_doc_count)
    except QuotaExceededError as e:
        raise HTTPException(
            status_code=429,
            detail=f"Document quota exceeded ({e.used}/{e.limit})",
            headers={"Retry-After": "3600", "X-Quota-Limit": str(e.limit)},
        )

    # Sanitize filename — centralized helper rejects empty + traversal sequences.
    from src.services.blobstore import (
        BlobStoreError,
        get_blob_store,
        sanitize_filename,
    )

    raw_name = file.filename or f"upload-{uuid.uuid4()}{ext}"
    try:
        safe_name = sanitize_filename(raw_name)
    except ValueError:
        safe_name = f"upload-{uuid.uuid4()}{ext}"
    source = safe_name

    meta: dict = {}
    if metadata:
        try:
            meta = json.loads(metadata)
        except json.JSONDecodeError:
            raise HTTPException(status_code=422, detail="Invalid metadata JSON")
        if not isinstance(meta, dict):
            raise HTTPException(status_code=422, detail="Metadata must be a JSON object")

    service = IngestionService(
        documents_collection=deps.documents_collection,
        chunks_collection=deps.chunks_collection,
    )

    document_id = await service.create_pending_document(
        tenant_id=tenant_id,
        title=title or os.path.splitext(source)[0],
        source=source,
        metadata=meta,
    )

    blob_store = get_blob_store()
    key = f"{tenant_id}/{document_id}/{safe_name}"
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    capped_source = _SizeCappedReader(file.file, max_bytes=max_bytes)
    try:
        blob_uri = await blob_store.put(key, capped_source, file.content_type)
    except _UploadTooLargeError:
        # BlobStore.put cleans up its own partial blob; mark the doc failed
        # so the dashboard reflects what happened, then return 413.
        await service.update_status(
            str(document_id), tenant_id, "failed", error_message="File too large"
        )
        logger.warning(
            "Upload rejected for doc=%s tenant=%s: exceeded %dMB cap",
            document_id,
            tenant_id,
            settings.max_upload_size_mb,
        )
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {settings.max_upload_size_mb}MB",
        )
    except BlobStoreError as e:
        await service.update_status(
            str(document_id), tenant_id, "failed", error_message="Upload failed"
        )
        logger.exception("Blob upload failed for doc=%s: %s", document_id, e)
        raise HTTPException(status_code=503, detail="Upload failed")

    try:
        task = ingest_document.delay(
            blob_uri=blob_uri,
            document_id=str(document_id),
            tenant_id=tenant_id,
            title=title or os.path.splitext(source)[0],
            source=source,
            metadata=meta,
        )
    except Exception:
        # Clean up blob and mark doc failed if Celery dispatch fails
        await blob_store.delete(blob_uri)
        await service.update_status(
            str(document_id), tenant_id, "failed", error_message="Task queue unavailable"
        )
        logger.exception("Failed to dispatch ingestion task for doc=%s", document_id)
        raise HTTPException(status_code=503, detail="Task queue unavailable")

    logger.info(
        "Ingestion dispatched: doc=%s, tenant=%s, task=%s, blob_uri=%s",
        document_id,
        tenant_id,
        task.id,
        blob_uri,
    )

    return IngestResponse(
        document_id=str(document_id),
        status="pending",
        task_id=task.id,
    )


@router.post("/ingest-url", response_model=IngestResponse, status_code=202)
async def ingest_url_endpoint(
    payload: IngestURLRequest,
    tenant_id: str = Depends(enforce_rate_limit),
    settings: Settings = Depends(_get_settings),
    deps: AgentDependencies = Depends(get_deps),
) -> IngestResponse:
    """Fetch a remote URL and ingest its contents.

    The URL is validated synchronously (scheme, hostname, DNS resolution to a
    public IP, no metadata endpoints) before a Celery task is dispatched.
    Returns 202 Accepted with the document_id and task_id.
    """
    # Pre-flight SSRF check at request time so callers see a meaningful 422
    # before we create a database row or enqueue a job.
    try:
        normalized = validate_url(payload.url, allow_private=settings.url_fetch_allow_private_ips)
    except URLValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    usage_service = UsageService(deps.usage_collection, deps.subscriptions_collection)
    current_doc_count = await deps.documents_collection.count_documents({"tenant_id": tenant_id})
    try:
        await usage_service.check_document_quota(tenant_id, current_doc_count)
    except QuotaExceededError as e:
        raise HTTPException(
            status_code=429,
            detail=f"Document quota exceeded ({e.used}/{e.limit})",
            headers={"Retry-After": "3600", "X-Quota-Limit": str(e.limit)},
        )

    service = IngestionService(
        documents_collection=deps.documents_collection,
        chunks_collection=deps.chunks_collection,
    )

    metadata = dict(payload.metadata or {})
    metadata["source_url"] = normalized

    document_id = await service.create_pending_document(
        tenant_id=tenant_id,
        title=payload.title or normalized,
        source=normalized,
        metadata=metadata,
    )

    try:
        task = ingest_url.delay(
            url=normalized,
            document_id=str(document_id),
            tenant_id=tenant_id,
            title=payload.title,
            metadata=metadata,
        )
    except Exception:
        await service.update_status(
            str(document_id), tenant_id, "failed", error_message="Task queue unavailable"
        )
        logger.exception("Failed to dispatch URL ingestion task for doc=%s", document_id)
        raise HTTPException(status_code=503, detail="Task queue unavailable")

    logger.info(
        "URL ingestion dispatched: doc=%s tenant=%s task=%s",
        document_id,
        tenant_id,
        task.id,
    )

    return IngestResponse(
        document_id=str(document_id),
        status="pending",
        task_id=task.id,
    )


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: str,
    tenant_id: str = Depends(get_tenant_id),
    deps: AgentDependencies = Depends(get_deps),
) -> DocumentStatusResponse:
    """Get document processing status.

    Returns current status, chunk count, and version for the given document.
    Returns 404 if document not found or belongs to a different tenant.
    """
    service = IngestionService(
        documents_collection=deps.documents_collection,
        chunks_collection=deps.chunks_collection,
    )

    doc = await service.get_document_status(document_id, tenant_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentStatusResponse(
        document_id=str(doc["_id"]),
        status=doc.get("status", "unknown"),
        chunk_count=doc.get("chunk_count", 0),
        version=doc.get("version", 1),
        error_message=doc.get("error_message"),
    )
