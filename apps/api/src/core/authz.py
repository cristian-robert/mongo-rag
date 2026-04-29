"""Role-based authorization helpers for dashboard JWT principals.

API-key requests do NOT carry a role and are rejected here. Use
``get_tenant_id`` (in ``core.tenant``) for endpoints that must accept API
keys; use these helpers for dashboard-only management endpoints.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request

from src.core.observability import set_request_context
from src.core.security import decode_jwt
from src.core.settings import load_settings
from src.models.user import UserRole, has_min_role

logger = logging.getLogger(__name__)

_API_KEY_PREFIX = "mrag_"


@dataclass(frozen=True)
class Principal:
    """An authenticated dashboard user."""

    user_id: str
    tenant_id: str
    role: str


async def get_principal(
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> Principal:
    """Decode a dashboard JWT and return the calling principal.

    Raises:
        HTTPException 401: missing / invalid token, or token lacks required claims.
        HTTPException 403: caller used an API key — keys cannot manage team.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authorization header with Bearer token is required",
        )

    token = authorization[7:]
    if token.startswith(_API_KEY_PREFIX):
        raise HTTPException(
            status_code=403,
            detail="API keys cannot access this endpoint",
        )

    settings = load_settings()
    payload = decode_jwt(token, settings.nextauth_secret)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    tenant_id = payload.get("tenant_id")
    user_id = payload.get("sub")
    role = payload.get("role")
    if not tenant_id or not user_id or not role:
        raise HTTPException(
            status_code=401,
            detail="Token missing required claims",
        )
    if role not in {r.value for r in UserRole}:
        raise HTTPException(status_code=401, detail="Token has unknown role claim")

    request.state.tenant_id = tenant_id
    set_request_context(tenant_id=tenant_id)
    return Principal(user_id=user_id, tenant_id=tenant_id, role=role)


def require_role(minimum: UserRole):
    """Build a FastAPI dependency that enforces a minimum role.

    Example::

        @router.post(...)
        async def endpoint(principal: Principal = Depends(require_role(UserRole.ADMIN))):
            ...
    """

    async def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        if not has_min_role(principal.role, minimum):
            logger.info(
                "rbac_denied",
                extra={
                    "tenant_id": principal.tenant_id,
                    "user_id": principal.user_id,
                    "role": principal.role,
                    "required": minimum.value,
                },
            )
            raise HTTPException(
                status_code=403,
                detail=f"Requires '{minimum.value}' role or higher",
            )
        return principal

    return _dep
