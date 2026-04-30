"""Tenant extraction from JWT or API key.

Three supported credential formats on `Authorization: Bearer <token>`:

1. `mrag_...` API key — validated against Postgres `public.api_keys` (issue
   #42). The legacy MongoDB-backed sha256 lookup is kept behind
   ``API_KEY_BACKEND=mongo`` for emergency rollback only.
2. Supabase user JWT — verified via JWKS or a configured shared secret;
   `tenant_id` is resolved from Postgres ``public.profiles`` keyed by the
   JWT ``sub`` (the Postgres trigger ``handle_new_user`` guarantees a
   profile per ``auth.users`` row, so a missing profile is a 401).
3. Legacy NextAuth.js JWT — verified with the shared `nextauth_secret`.

Routing between (2) and (3) is done by a cheap `iss` peek before
verification. Verification of each path is independent: failure on the
Supabase path never falls through to the NextAuth path on the same token,
which avoids algorithm-confusion / fall-through bypasses.
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

import asyncpg
from fastapi import Depends, Header, HTTPException, Request

from src.auth import api_keys as pg_api_keys
from src.auth.profiles import lookup_profile
from src.core.dependencies import AgentDependencies
from src.core.deps import get_deps
from src.core.observability import set_request_context
from src.core.security import decode_jwt
from src.core.settings import Settings, load_settings
from src.core.supabase_auth import (
    SupabaseClaims,
    _looks_like_supabase_token,
    verify_supabase_jwt,
)

logger = logging.getLogger(__name__)

_API_KEY_PREFIX = pg_api_keys.KEY_PREFIX


async def get_tenant_id(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    deps: AgentDependencies = Depends(get_deps),
) -> str:
    """Extract tenant_id from JWT or API key in the Authorization header.

    Args:
        request: The incoming request (used to set tenant context on state
            and read the Postgres pool from app.state).
        authorization: Authorization header value.
        deps: Application dependencies for DB access.

    Returns:
        Validated tenant_id string.

    Raises:
        HTTPException: 401 if the credential is missing, invalid, or
            cannot be resolved to a tenant.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authorization header with Bearer token is required",
        )

    token = authorization[7:]

    if token.startswith(_API_KEY_PREFIX):
        tenant_id = await _resolve_api_key(token, request, deps)
    else:
        pool = getattr(request.app.state, "pg_pool", None)
        tenant_id = await _resolve_jwt(token, pool)

    request.state.tenant_id = tenant_id
    set_request_context(tenant_id=tenant_id)
    return tenant_id


async def _resolve_api_key(raw_key: str, request: Request, deps: AgentDependencies) -> str:
    """Validate an API key and return its tenant_id.

    Postgres is the default. Falls back to Mongo when:
      - ``API_KEY_BACKEND=mongo`` is set, OR
      - the Postgres pool is unavailable (graceful degradation during
        the rollout window).

    All failure modes return the same opaque 401 to avoid leaking which
    branch failed (revoked vs. unknown vs. backend down).
    """
    settings = load_settings()
    pool = getattr(request.app.state, "pg_pool", None)

    if settings.api_key_backend == "postgres" and pool is not None:
        principal = await pg_api_keys.verify_key(pool, raw_key)
        if principal is None:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return principal.tenant_id

    return await _resolve_api_key_mongo(raw_key, deps)


async def _resolve_api_key_mongo(raw_key: str, deps: AgentDependencies) -> str:
    """Mongo-backed validation kept for rollback (set ``API_KEY_BACKEND=mongo``)."""
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    doc = await deps.api_keys_collection.find_one({"key_hash": key_hash})

    if not doc:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if doc.get("is_revoked", False):
        # Same opaque 401 as unknown-key — don't leak revocation state.
        raise HTTPException(status_code=401, detail="Invalid API key")

    await deps.api_keys_collection.update_one(
        {"key_hash": key_hash},
        {"$set": {"last_used_at": datetime.now(timezone.utc)}},
    )

    return doc["tenant_id"]


async def get_tenant_id_from_jwt(
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> str:
    """Extract tenant_id from JWT only. Rejects API keys.

    Used by endpoints that must only be reachable from a dashboard session
    (e.g., key management), not from a programmatic API key. The JWT path
    no longer needs ``AgentDependencies`` (post-#75) — Settings load directly
    and the Postgres pool is read off ``request.app.state``.
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

    pool = getattr(request.app.state, "pg_pool", None)
    tenant_id = await _resolve_jwt(token, pool)
    request.state.tenant_id = tenant_id
    set_request_context(tenant_id=tenant_id)
    return tenant_id


async def _resolve_jwt(token: str, pool: Optional[asyncpg.Pool]) -> str:
    """Validate a JWT (Supabase or legacy NextAuth) and return its tenant_id.

    Routing rule: if the token's unverified `iss` matches the configured
    Supabase issuer, only the Supabase path is tried. Otherwise only the
    NextAuth path is tried. **No fall-through** between paths — a Supabase
    token with a bad signature must NOT fall back to HS256/NextAuth
    verification (algorithm-confusion guard).

    The Supabase path needs ``pool`` to look up the caller's profile in
    Postgres. The NextAuth path is self-contained (settings only).
    """
    settings = load_settings()

    if _looks_like_supabase_token(token, settings):
        try:
            claims = await verify_supabase_jwt(token, settings)
        except ValueError as e:
            logger.debug("Supabase JWT rejected: %s", e)
            raise HTTPException(status_code=401, detail="Invalid or expired token") from None
        return await _tenant_id_from_supabase_claims(claims, pool)

    return _resolve_nextauth_jwt(token, settings)


def _resolve_nextauth_jwt(token: str, settings: Settings) -> str:
    """Verify a legacy NextAuth-issued JWT (HS256 with the shared secret)."""
    payload = decode_jwt(token, settings.nextauth_secret)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Token missing tenant_id claim")

    return tenant_id


async def _tenant_id_from_supabase_claims(
    claims: SupabaseClaims, pool: Optional[asyncpg.Pool]
) -> str:
    """Resolve tenant_id from Supabase claims via Postgres ``public.profiles``.

    The profile row (populated by the ``handle_new_user`` trigger) is the
    sole source of truth — JWT-supplied ``tenant_id`` claims are NOT
    consulted. This matches the web frontend behaviour and prevents a
    user-editable claim from overriding the server-side mapping.

    Fail-closed: if the pool is missing or the profile is absent, raise 401.
    """
    if pool is None:
        logger.error("tenant_pg_pool_unavailable", extra={"sub": claims.sub})
        raise HTTPException(status_code=401, detail="Authentication backend unavailable")

    profile = await lookup_profile(pool, claims.sub)
    if profile is None:
        logger.info(
            "supabase_user_without_tenant",
            extra={"sub": claims.sub, "has_email": claims.email is not None},
        )
        raise HTTPException(status_code=401, detail="User has no tenant assigned")
    return profile.tenant_id
