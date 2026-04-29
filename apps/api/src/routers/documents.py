"""Document CRUD endpoints (list, get, patch, delete, reingest).

These endpoints are tenant-scoped via the JWT-or-API-key dependency.
The tenant_id is ALWAYS derived from the auth principal — it is never
read from request body or query string.

Companion to ``routers/ingest.py`` which owns POST /ingest and the
status polling endpoint at /{id}/status.
"""

from __future__ import annotations

import logging
import os
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status

from src.core.dependencies import AgentDependencies
from src.core.deps import get_deps
from src.core.tenant import get_tenant_id
from src.models.api import (
    BulkDeleteRequest,
    BulkDeleteResponse,
    DocumentListResponse,
    DocumentRecord,
    DocumentUpdateRequest,
    ReingestResponse,
)
from src.services.ingestion.service import IngestionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


def _ingestion_service(
    deps: AgentDependencies = Depends(get_deps),
) -> IngestionService:
    return IngestionService(
        documents_collection=deps.documents_collection,
        chunks_collection=deps.chunks_collection,
    )


def _to_record(doc: dict) -> DocumentRecord:
    """Convert a stored document dict to the API response model.

    Derives ``format`` from the file extension of ``source`` if not stored.
    """
    source = doc.get("source", "") or ""
    fmt = doc.get("format")
    if not fmt:
        ext = os.path.splitext(source)[1].lower().lstrip(".")
        fmt = ext or ""

    return DocumentRecord(
        document_id=str(doc["_id"]),
        title=doc.get("title", ""),
        source=source,
        status=str(doc.get("status", "unknown")),
        chunk_count=int(doc.get("chunk_count", 0) or 0),
        format=fmt,
        size_bytes=doc.get("size_bytes"),
        metadata=doc.get("metadata") or {},
        version=int(doc.get("version", 1) or 1),
        error_message=doc.get("error_message"),
        created_at=doc["created_at"],
        updated_at=doc.get("updated_at", doc["created_at"]),
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    service: Annotated[IngestionService, Depends(_ingestion_service)],
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: Optional[Literal["pending", "processing", "ready", "failed"]] = Query(
        default=None, alias="status"
    ),
    search: Optional[str] = Query(default=None, max_length=200),
    sort: Literal["created_at", "updated_at", "title", "status"] = Query(default="created_at"),
    order: Literal["asc", "desc"] = Query(default="desc"),
) -> DocumentListResponse:
    """List documents for the authenticated tenant.

    Pagination is offset-based (page/page_size). Tenant_id is forced from
    the JWT/API-key — it cannot be supplied by the caller.
    """
    items, total = await service.list_documents(
        tenant_id=tenant_id,
        page=page,
        page_size=page_size,
        status=status_filter,
        search=search,
        sort=sort,
        order=order,
    )
    return DocumentListResponse(
        items=[_to_record(d) for d in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.delete("", response_model=BulkDeleteResponse)
async def bulk_delete_documents(
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    service: Annotated[IngestionService, Depends(_ingestion_service)],
    body: BulkDeleteRequest = Body(...),
) -> BulkDeleteResponse:
    """Cascade-delete a list of documents (and their chunks) for this tenant.

    Tenant scope is enforced per-id; ids that do not belong to this tenant
    are silently ignored (counted as not deleted) to prevent enumeration.
    """
    deleted = await service.bulk_delete_with_cascade(body.ids, tenant_id)
    logger.info(
        "bulk_delete_documents tenant=%s requested=%d deleted=%d",
        tenant_id,
        len(body.ids),
        deleted,
    )
    return BulkDeleteResponse(requested=len(body.ids), deleted=deleted)


@router.get("/{document_id}", response_model=DocumentRecord)
async def get_document(
    document_id: str,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    service: Annotated[IngestionService, Depends(_ingestion_service)],
) -> DocumentRecord:
    """Fetch a single document. 404 for missing OR cross-tenant ids."""
    doc = await service.get_document(document_id, tenant_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _to_record(doc)


@router.patch("/{document_id}", response_model=DocumentRecord)
async def update_document(
    document_id: str,
    body: DocumentUpdateRequest,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    service: Annotated[IngestionService, Depends(_ingestion_service)],
) -> DocumentRecord:
    """Update title and/or metadata. Other fields are immutable here."""
    if body.title is None and body.metadata is None:
        raise HTTPException(status_code=422, detail="No fields to update")

    updated = await service.update_metadata(
        document_id=document_id,
        tenant_id=tenant_id,
        title=body.title,
        metadata=body.metadata,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Document not found")
    return _to_record(updated)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    service: Annotated[IngestionService, Depends(_ingestion_service)],
) -> Response:
    """Cascade-delete a document and all of its chunks.

    Atomic via a Mongo transaction when supported; falls back to a
    sequenced delete (chunks first, then doc) on standalone deployments.
    """
    deleted = await service.delete_document_with_cascade(document_id, tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{document_id}/reingest", response_model=ReingestResponse, status_code=202)
async def reingest_document_endpoint(
    document_id: str,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    service: Annotated[IngestionService, Depends(_ingestion_service)],
) -> ReingestResponse:
    """Mark a document for re-processing.

    Flips status back to ``pending`` so the worker can re-chunk and re-embed
    on its next sweep. Refuses if the document is currently ``processing``
    to avoid racing the existing worker run.
    """
    updated = await service.mark_for_reingestion(document_id, tenant_id)
    if not updated:
        # Could be: missing, wrong tenant, OR already in-flight.
        # We can't distinguish without an extra read — but a second read
        # could leak existence to other tenants, so return 404/409 only
        # after confirming tenant ownership.
        existing = await service.get_document(document_id, tenant_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Document not found")
        raise HTTPException(
            status_code=409,
            detail="Document is currently processing; reingest not allowed",
        )
    return ReingestResponse(document_id=str(updated["_id"]), status=updated["status"])
