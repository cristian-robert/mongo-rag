"""Tenant extraction from JWT or API key.

Three supported credential formats on `Authorization: Bearer <token>`:

1. `mrag_...` API key — hashed and looked up in the api_keys collection.
2. Supabase user JWT — verified via JWKS or a configured shared secret;
   `tenant_id` is taken from claims or, as a fallback, derived from the
   user document keyed by Supabase `sub`.
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

from fastapi import Depends, Header, HTTPException, Request

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

_API_KEY_PREFIX = "mrag_"


async def get_tenant_id(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    deps: AgentDependencies = Depends(get_deps),
) -> str:
    """Extract tenant_id from JWT or API key in the Authorization header.

    Args:
        request: The incoming request (used to set tenant context on state).
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
        tenant_id = await _resolve_api_key(token, deps)
    else:
        tenant_id = await _resolve_jwt(token, deps)

    request.state.tenant_id = tenant_id
    set_request_context(tenant_id=tenant_id)
    return tenant_id


async def _resolve_api_key(raw_key: str, deps: AgentDependencies) -> str:
    """Validate an API key and return its tenant_id."""
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    doc = await deps.api_keys_collection.find_one({"key_hash": key_hash})

    if not doc:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if doc.get("is_revoked", False):
        raise HTTPException(status_code=401, detail="API key has been revoked")

    await deps.api_keys_collection.update_one(
        {"key_hash": key_hash},
        {"$set": {"last_used_at": datetime.now(timezone.utc)}},
    )

    return doc["tenant_id"]


async def get_tenant_id_from_jwt(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    deps: AgentDependencies = Depends(get_deps),
) -> str:
    """Extract tenant_id from JWT only. Rejects API keys.

    Used by endpoints that must only be reachable from a dashboard session
    (e.g., key management), not from a programmatic API key.
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

    tenant_id = await _resolve_jwt(token, deps)
    request.state.tenant_id = tenant_id
    set_request_context(tenant_id=tenant_id)
    return tenant_id


async def _resolve_jwt(token: str, deps: AgentDependencies) -> str:
    """Validate a JWT (Supabase or legacy NextAuth) and return its tenant_id.

    Routing rule: if the token's unverified `iss` matches the configured
    Supabase issuer, only the Supabase path is tried. Otherwise only the
    NextAuth path is tried. **No fall-through** between paths — a Supabase
    token with a bad signature must NOT fall back to HS256/NextAuth
    verification (algorithm-confusion guard).
    """
    settings = deps.settings if isinstance(deps.settings, Settings) else load_settings()

    if _looks_like_supabase_token(token, settings):
        try:
            claims = await verify_supabase_jwt(token, settings)
        except ValueError as e:
            logger.debug("Supabase JWT rejected: %s", e)
            raise HTTPException(status_code=401, detail="Invalid or expired token") from None
        return await _tenant_id_from_supabase_claims(claims, deps)

    # Legacy NextAuth path
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
    claims: SupabaseClaims, deps: AgentDependencies
) -> str:
    """Resolve tenant_id from Supabase claims, falling back to a DB lookup.

    Order of preference:
        1. `tenant_id` from claims (server-controlled `app_metadata` is best).
        2. Lookup in the `users` collection by `supabase_user_id` (the JWT `sub`).
        3. As a last resort, lookup by email.

    Fail-closed: if no tenant_id can be determined, raise 401.
    """
    if claims.tenant_id:
        return claims.tenant_id

    users = deps.users_collection
    user_doc = await users.find_one({"supabase_user_id": claims.sub})
    if not user_doc and claims.email:
        user_doc = await users.find_one({"email": claims.email.lower()})

    tenant_id = user_doc.get("tenant_id") if user_doc else None
    if not tenant_id:
        logger.info(
            "supabase_user_without_tenant",
            extra={"sub": claims.sub, "has_email": claims.email is not None},
        )
        raise HTTPException(status_code=401, detail="User has no tenant assigned")
    return tenant_id


