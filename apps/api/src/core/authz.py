"""Role-based authorization helpers for dashboard JWT principals.

API-key requests do NOT carry a role and are rejected here. Use
``get_tenant_id`` (in ``core.tenant``) for endpoints that must accept API
keys; use these helpers for dashboard-only management endpoints.

Supports both Supabase-issued JWTs (post-migration) and legacy NextAuth
HS256 tokens. Routing between paths is done by a cheap ``iss`` peek; there
is **no fall-through** between paths — a Supabase token with a bad
signature must NOT fall back to the NextAuth verifier (algorithm-confusion
guard, mirroring ``core/tenant.py``).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request

from src.core.dependencies import AgentDependencies
from src.core.deps import get_deps
from src.core.observability import set_request_context
from src.core.security import decode_jwt
from src.core.settings import load_settings
from src.core.supabase_auth import (
    SupabaseClaims,
    _looks_like_supabase_token,
    verify_supabase_jwt,
)
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
    deps: AgentDependencies = Depends(get_deps),
) -> Principal:
    """Decode a dashboard JWT (Supabase or legacy NextAuth) and return the principal.

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

    if _looks_like_supabase_token(token, settings):
        try:
            claims = await verify_supabase_jwt(token, settings)
        except ValueError as exc:
            logger.debug("Supabase JWT rejected by authz.get_principal: %s", exc)
            raise HTTPException(status_code=401, detail="Invalid or expired token") from None
        principal = await _principal_from_supabase_claims(claims, deps)
    else:
        principal = _principal_from_nextauth(token, settings)

    request.state.tenant_id = principal.tenant_id
    set_request_context(tenant_id=principal.tenant_id)
    return principal


def _principal_from_nextauth(token: str, settings) -> Principal:
    """Verify a legacy NextAuth-issued HS256 token and build a Principal.

    Kept for rollback safety until every dashboard caller has migrated to
    Supabase Auth.
    """
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

    return Principal(user_id=user_id, tenant_id=tenant_id, role=role)


async def _principal_from_supabase_claims(
    claims: SupabaseClaims, deps: AgentDependencies
) -> Principal:
    """Resolve a Principal from verified Supabase claims.

    Tenant precedence:
        1. ``tenant_id`` claim (server-controlled ``app_metadata`` is preferred).
        2. ``users`` doc keyed by ``supabase_user_id`` (the JWT ``sub``).
        3. ``users`` doc keyed by email.

    Role precedence:
        1. ``users`` doc ``role`` field, if recognized.
        2. ``UserRole.MEMBER`` as a safe default (RBAC fail-closed for
           privileged routes — admin/owner endpoints will return 403).

    Fail-closed: if no ``tenant_id`` can be determined, raise 401. Mirrors the
    pattern in ``core/tenant.py::_tenant_id_from_supabase_claims`` so the two
    auth chokepoints behave consistently.
    """
    users = deps.users_collection
    user_doc = await users.find_one({"supabase_user_id": claims.sub})
    if user_doc is None and claims.email:
        user_doc = await users.find_one({"email": claims.email.lower()})

    tenant_id = claims.tenant_id or (user_doc.get("tenant_id") if user_doc else None)
    if not tenant_id:
        logger.info(
            "supabase_user_without_tenant",
            extra={"sub": claims.sub, "has_email": claims.email is not None},
        )
        raise HTTPException(status_code=401, detail="User has no tenant assigned")

    raw_role = (user_doc or {}).get("role")
    valid_roles = {r.value for r in UserRole}
    role = raw_role if raw_role in valid_roles else UserRole.MEMBER.value

    user_id = (
        str(user_doc["_id"])
        if user_doc is not None and user_doc.get("_id") is not None
        else claims.sub
    )

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
