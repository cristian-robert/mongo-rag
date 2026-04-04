"""API key management endpoints."""

import logging

from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException

from src.core.dependencies import AgentDependencies
from src.core.deps import get_deps
from src.core.tenant import get_tenant_id
from src.models.api import (
    CreateKeyRequest,
    CreateKeyResponse,
    KeyListResponse,
    KeyResponse,
    MessageResponse,
)
from src.services.api_key import APIKeyService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/keys", tags=["api-keys"])


def _get_api_key_service(deps: AgentDependencies = Depends(get_deps)) -> APIKeyService:
    """Create APIKeyService with injected collection."""
    return APIKeyService(api_keys_collection=deps.api_keys_collection)


@router.post("", response_model=CreateKeyResponse, status_code=201)
async def create_key(
    body: CreateKeyRequest,
    tenant_id: str = Depends(get_tenant_id),
    service: APIKeyService = Depends(_get_api_key_service),
):
    """Generate a new API key. The raw key is returned once and cannot be retrieved again."""
    result = await service.create_key(
        tenant_id=tenant_id,
        name=body.name,
        permissions=body.permissions,
    )
    return CreateKeyResponse(**result)


@router.get("", response_model=KeyListResponse)
async def list_keys(
    tenant_id: str = Depends(get_tenant_id),
    service: APIKeyService = Depends(_get_api_key_service),
):
    """List all API keys for the authenticated tenant."""
    keys = await service.list_keys(tenant_id)
    return KeyListResponse(keys=[KeyResponse(**k) for k in keys])


@router.delete("/{key_id}", response_model=MessageResponse)
async def revoke_key(
    key_id: str,
    tenant_id: str = Depends(get_tenant_id),
    service: APIKeyService = Depends(_get_api_key_service),
):
    """Revoke an API key (soft delete)."""
    try:
        revoked = await service.revoke_key(key_id=key_id, tenant_id=tenant_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid key ID format")

    if not revoked:
        raise HTTPException(status_code=404, detail="API key not found")

    return MessageResponse(message="API key revoked")
