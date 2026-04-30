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

import asyncpg
from fastapi import Depends, Header, HTTPException, Request

from src.auth.profiles import lookup_profile
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
) -> Principal:
    """Decode a dashboard JWT (Supabase or legacy NextAuth) and return the principal.

    The Supabase path resolves tenant + role from Postgres ``public.profiles``;
    the pool is read off ``request.app.state.pg_pool`` (mirroring
    ``core/deps.get_pg_pool``). The NextAuth path is self-contained.

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
        pool = getattr(request.app.state, "pg_pool", None)
        principal = await _principal_from_supabase_claims(claims, pool)
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
    claims: SupabaseClaims, pool: Optional[asyncpg.Pool]
) -> Principal:
    """Resolve a Principal from verified Supabase claims via Postgres ``profiles``.

    The Postgres ``handle_new_user`` trigger populates ``public.profiles``
    atomically on signup, so a missing profile is a real "not provisioned"
    state and we 401 — there is no Mongo fallback in the new world. The
    JWT-supplied ``tenant_id`` is intentionally NOT consulted; the profile
    row is the sole source of truth and matches the web frontend
    behaviour.

    An unrecognized role falls back to ``UserRole.MEMBER`` so privileged
    endpoints still return 403 instead of mis-elevating the caller.
    """
    if pool is None:
        logger.error("authz_pg_pool_unavailable", extra={"sub": claims.sub})
        raise HTTPException(status_code=401, detail="Authentication backend unavailable")

    profile = await lookup_profile(pool, claims.sub)
    if profile is None:
        logger.info(
            "supabase_user_without_profile",
            extra={"sub": claims.sub, "has_email": claims.email is not None},
        )
        raise HTTPException(status_code=401, detail="User has no tenant assigned")

    valid_roles = {r.value for r in UserRole}
    role = profile.role if profile.role in valid_roles else UserRole.MEMBER.value

    return Principal(user_id=profile.id, tenant_id=profile.tenant_id, role=role)


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
