"""Tenant extraction from JWT or API key."""

import logging
from typing import Optional

from fastapi import Header, HTTPException

from src.core.security import decode_jwt
from src.core.settings import load_settings

logger = logging.getLogger(__name__)


async def get_tenant_id(
    authorization: Optional[str] = Header(default=None),
) -> str:
    """Extract tenant_id from JWT in the Authorization header.

    Expects: Authorization: Bearer <jwt>
    JWT must contain a 'tenant_id' claim.

    Args:
        authorization: Authorization header value.

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
    settings = load_settings()
    payload = decode_jwt(token, settings.nextauth_secret)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Token missing tenant_id claim")

    return tenant_id
