"""API key management endpoints (Postgres-backed, #42).

Writes go to ``public.api_keys`` in Postgres. The Mongo path is kept only
as an emergency rollback (``API_KEY_BACKEND=mongo``) and is not exposed
through this router — these endpoints always use Postgres.

RBAC (#29):
  - ``POST``/``DELETE`` require ``UserRole.ADMIN``
  - ``GET`` requires ``UserRole.MEMBER``

Permission lists are not persisted in the Postgres schema (#42); we accept
them on input for forward-compat but always return the implicit default set.
"""

import logging
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from src.auth import api_keys as pg_api_keys
from src.core.authz import Principal, require_role
from src.core.deps import get_pg_pool
from src.models.api import (
    CreateKeyRequest,
    CreateKeyResponse,
    KeyListResponse,
    KeyResponse,
    MessageResponse,
)
from src.models.user import UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/keys", tags=["api-keys"])

# Backward-compat: the new schema does not store per-key permissions, so
# every key implicitly carries the full default set. The web client (#46)
# still expects a `permissions` array on responses.
_DEFAULT_PERMISSIONS = ["chat", "search"]


def _require_pool(pool: Optional[asyncpg.Pool]) -> asyncpg.Pool:
    if pool is None:
        # Fail closed: management endpoints require Postgres in the new world.
        raise HTTPException(
            status_code=503,
            detail="API key store is unavailable",
        )
    return pool


@router.post("", response_model=CreateKeyResponse, status_code=201)
async def create_key(
    body: CreateKeyRequest,
    principal: Principal = Depends(require_role(UserRole.ADMIN)),
    pool: Optional[asyncpg.Pool] = Depends(get_pg_pool),
):
    """Generate a new API key. The raw key is returned once and cannot be retrieved."""
    pool = _require_pool(pool)
    result = await pg_api_keys.create_key(pool=pool, tenant_id=principal.tenant_id, name=body.name)
    return CreateKeyResponse(
        raw_key=result["raw_key"],
        key_prefix=result["key_prefix"],
        name=result["name"],
        permissions=body.permissions or list(_DEFAULT_PERMISSIONS),
        created_at=result["created_at"],
    )


@router.get("", response_model=KeyListResponse)
async def list_keys(
    principal: Principal = Depends(require_role(UserRole.MEMBER)),
    pool: Optional[asyncpg.Pool] = Depends(get_pg_pool),
):
    """List all API keys for the authenticated tenant."""
    pool = _require_pool(pool)
    rows = await pg_api_keys.list_keys(pool=pool, tenant_id=principal.tenant_id)
    return KeyListResponse(
        keys=[
            KeyResponse(
                id=r["id"],
                key_prefix=r["key_prefix"],
                name=r["name"],
                permissions=list(_DEFAULT_PERMISSIONS),
                is_revoked=r["is_revoked"],
                last_used_at=r["last_used_at"],
                created_at=r["created_at"],
            )
            for r in rows
        ]
    )


@router.delete("/{key_id}", response_model=MessageResponse)
async def revoke_key(
    key_id: str,
    principal: Principal = Depends(require_role(UserRole.ADMIN)),
    pool: Optional[asyncpg.Pool] = Depends(get_pg_pool),
):
    """Revoke an API key (soft delete: sets revoked_at)."""
    pool = _require_pool(pool)
    try:
        revoked = await pg_api_keys.revoke_key(
            pool=pool, key_id=key_id, tenant_id=principal.tenant_id
        )
    except (ValueError, asyncpg.DataError):
        raise HTTPException(status_code=400, detail="Invalid key ID format")

    if not revoked:
        raise HTTPException(status_code=404, detail="API key not found")

    return MessageResponse(message="API key revoked")
