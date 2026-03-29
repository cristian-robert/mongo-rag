"""Document ingestion endpoints."""

import json
import logging
import os
import shutil
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from src.core.settings import Settings, load_settings
from src.core.tenant import get_tenant_id
from src.models.api import DocumentStatusResponse, IngestResponse
from src.services.ingestion.service import IngestionService
from src.worker import ingest_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

SUPPORTED_EXTENSIONS = {
    ".pdf", ".txt", ".md", ".markdown", ".docx", ".doc",
    ".pptx", ".ppt", ".xlsx", ".xls", ".html", ".htm",
}


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
    tenant_id: str = Depends(get_tenant_id),
    settings: Settings = Depends(_get_settings),
) -> IngestResponse:
    """Upload and ingest a document.

    Validates the file, creates a pending document record, saves the file
    to a temp directory, and dispatches a Celery task for processing.

    Returns 202 Accepted immediately with document_id and task_id.
    """
    ext = _validate_file(file, settings)
    source = file.filename or f"upload-{uuid.uuid4()}{ext}"

    meta: dict = {}
    if metadata:
        try:
            meta = json.loads(metadata)
        except json.JSONDecodeError:
            raise HTTPException(status_code=422, detail="Invalid metadata JSON")

    from src.main import _deps

    service = IngestionService(
        documents_collection=_deps.documents_collection,
        chunks_collection=_deps.chunks_collection,
    )

    document_id = await service.create_pending_document(
        tenant_id=tenant_id,
        title=title or os.path.splitext(source)[0],
        source=source,
        metadata=meta,
    )

    temp_dir = os.path.join(settings.upload_temp_dir, str(uuid.uuid4()))
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, source)

    with open(temp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    task = ingest_document.delay(
        temp_path=temp_path,
        document_id=str(document_id),
        tenant_id=tenant_id,
        title=title or os.path.splitext(source)[0],
        source=source,
        metadata=meta,
    )

    logger.info(
        "Ingestion dispatched: doc=%s, tenant=%s, task=%s",
        document_id, tenant_id, task.id,
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
) -> DocumentStatusResponse:
    """Get document processing status.

    Returns current status, chunk count, and version for the given document.
    Returns 404 if document not found or belongs to a different tenant.
    """
    from src.main import _deps

    service = IngestionService(
        documents_collection=_deps.documents_collection,
        chunks_collection=_deps.chunks_collection,
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
