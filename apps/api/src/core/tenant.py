"""Tenant extraction from JWT or API key."""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, Header, HTTPException

from src.core.dependencies import AgentDependencies
from src.core.deps import get_deps
from src.core.security import decode_jwt
from src.core.settings import load_settings

logger = logging.getLogger(__name__)

_API_KEY_PREFIX = "mrag_"


async def get_tenant_id(
    authorization: Optional[str] = Header(default=None),
    deps: AgentDependencies = Depends(get_deps),
) -> str:
    """Extract tenant_id from JWT or API key in the Authorization header.

    Detects auth method by the 'mrag_' prefix:
    - 'mrag_...' → API key path (hash and look up in api_keys collection)
    - Otherwise → JWT path (decode with nextauth_secret)

    Args:
        authorization: Authorization header value.
        deps: Application dependencies for DB access.

    Returns:
        Validated tenant_id string.

    Raises:
        HTTPException: 401 if token is missing, invalid, or lacks tenant_id.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authorization header with Bearer token is required",
        )

    token = authorization[7:]  # Strip "Bearer "

    if token.startswith(_API_KEY_PREFIX):
        return await _resolve_api_key(token, deps)

    return _resolve_jwt(token)


async def _resolve_api_key(raw_key: str, deps: AgentDependencies) -> str:
    """Validate an API key and return its tenant_id.

    Args:
        raw_key: The full API key string (mrag_...).
        deps: Application dependencies for DB access.

    Returns:
        tenant_id from the API key document.

    Raises:
        HTTPException: 401 if key is invalid or revoked.
    """
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    doc = await deps.api_keys_collection.find_one({"key_hash": key_hash})

    if not doc:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if doc.get("is_revoked", False):
        raise HTTPException(status_code=401, detail="API key has been revoked")

    # Update last_used_at (blocking at MVP scale; optimize if needed)
    await deps.api_keys_collection.update_one(
        {"key_hash": key_hash},
        {"$set": {"last_used_at": datetime.now(timezone.utc)}},
    )

    return doc["tenant_id"]


async def get_tenant_id_from_jwt(
    authorization: Optional[str] = Header(default=None),
) -> str:
    """Extract tenant_id from JWT only. Rejects API keys.

    Use this for endpoints that must only be accessible via dashboard
    sessions (e.g., key management), not via API keys.

    Args:
        authorization: Authorization header value.

    Returns:
        Validated tenant_id string.

    Raises:
        HTTPException: 401 if token is missing, invalid, or an API key.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authorization header with Bearer token is required",
        )

    token = authorization[7:]  # Strip "Bearer "

    if token.startswith(_API_KEY_PREFIX):
        raise HTTPException(
            status_code=403,
            detail="API keys cannot access this endpoint",
        )

    return _resolve_jwt(token)


def _resolve_jwt(token: str) -> str:
    """Validate a JWT and return its tenant_id.

    Args:
        token: JWT token string.

    Returns:
        tenant_id from the JWT payload.

    Raises:
        HTTPException: 401 if token is invalid or lacks tenant_id.
    """
    settings = load_settings()
    payload = decode_jwt(token, settings.nextauth_secret)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Token missing tenant_id claim")

    return tenant_id
