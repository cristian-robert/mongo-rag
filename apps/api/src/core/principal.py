"""Authenticated principal abstraction.

A ``Principal`` is the immutable view of "who is making this request" derived
from a verified JWT or API key. Every MongoDB query that touches tenant-scoped
data MUST source ``tenant_id`` from a Principal — never from request input.

The chokepoint enforced by this module:

1. ``get_principal`` — FastAPI dependency that decodes the bearer token and
   returns a ``Principal``. Mirrors the existing ``get_tenant_id`` dependency
   so existing routers can migrate one at a time.
2. ``tenant_filter(principal, **extra)`` — builds a MongoDB filter dict whose
   ``tenant_id`` is locked to the principal. Callers pass extra match
   conditions; ``tenant_id`` always wins on collisions.
3. ``tenant_doc(principal, **fields)`` — builds an insert document with
   ``tenant_id`` locked to the principal.

These helpers are intentionally tiny — they exist so the audit lint test can
prove every Mongo call site either (a) uses one of them, or (b) is on a
documented allow-list (auth-by-key lookups, internal infra collections).
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Depends, Header, HTTPException, Request

from src.core.dependencies import AgentDependencies
from src.core.deps import get_deps
from src.core.observability import set_request_context
from src.core.security import decode_jwt
from src.core.settings import load_settings

logger = logging.getLogger(__name__)

_API_KEY_PREFIX = "mrag_"


@dataclass(frozen=True)
class Principal:
    """Verified caller identity.

    Frozen because every line of business code assumes ``principal.tenant_id``
    cannot change after authentication.
    """

    tenant_id: str
    auth_method: str  # "jwt" or "api_key"
    user_id: Optional[str] = None
    role: Optional[str] = None
    permissions: tuple[str, ...] = ()
    api_key_id: Optional[str] = None

    def require_jwt(self) -> "Principal":
        """Reject this principal if it came from an API key.

        Used by dashboard-only endpoints (key management, billing, analytics).
        """
        if self.auth_method != "jwt":
            raise HTTPException(
                status_code=403,
                detail="API keys cannot access this endpoint",
            )
        return self

    def require_permission(self, permission: str) -> "Principal":
        """Reject the request if an API key principal lacks the permission.

        JWT principals have implicit full access — RBAC for users lives in #29.
        """
        if self.auth_method == "api_key" and permission not in self.permissions:
            raise HTTPException(
                status_code=403,
                detail=f"API key missing required permission: {permission}",
            )
        return self


# -- FastAPI dependencies ----------------------------------------------------


async def get_principal(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    deps: AgentDependencies = Depends(get_deps),
) -> Principal:
    """Resolve the authenticated principal from the Authorization header.

    Detects auth method by the ``mrag_`` prefix. Mirrors ``get_tenant_id``
    but returns the richer ``Principal`` and records the result on
    ``request.state`` for the tenant-guard middleware.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authorization header with Bearer token is required",
        )

    token = authorization[7:]
    if token.startswith(_API_KEY_PREFIX):
        principal = await _resolve_api_key(token, deps)
    else:
        principal = _resolve_jwt(token)

    request.state.tenant_id = principal.tenant_id
    request.state.principal = principal
    set_request_context(tenant_id=principal.tenant_id)
    return principal


async def get_principal_jwt_only(
    principal: Principal = Depends(get_principal),
) -> Principal:
    """Variant that rejects API-key callers — for dashboard-only endpoints."""
    return principal.require_jwt()


# -- Resolvers ---------------------------------------------------------------


async def _resolve_api_key(raw_key: str, deps: AgentDependencies) -> Principal:
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

    permissions = tuple(doc.get("permissions") or ())
    return Principal(
        tenant_id=doc["tenant_id"],
        auth_method="api_key",
        permissions=permissions,
        api_key_id=str(doc.get("_id")) if doc.get("_id") is not None else None,
    )


def _resolve_jwt(token: str) -> Principal:
    settings = load_settings()
    payload = decode_jwt(token, settings.nextauth_secret)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Token missing tenant_id claim")

    return Principal(
        tenant_id=tenant_id,
        auth_method="jwt",
        user_id=payload.get("sub"),
        role=payload.get("role"),
    )


# -- Query helpers (chokepoint for tenant isolation) -------------------------


def tenant_filter(principal: Principal, **extra: Any) -> dict[str, Any]:
    """Build a MongoDB filter that always pins ``tenant_id`` to the principal.

    Callers MUST use this helper instead of building filters by hand whenever
    they need the result to be tenant-scoped. The function intentionally
    overrides any ``tenant_id`` the caller might have passed in ``extra`` —
    the principal is the only source of truth.
    """
    if not principal.tenant_id:
        # Defense in depth — Principal construction already guarantees this.
        raise HTTPException(status_code=401, detail="Authenticated tenant required")
    if "tenant_id" in extra and extra["tenant_id"] != principal.tenant_id:
        logger.warning(
            "tenant_filter_overrode_caller_tenant_id",
            extra={
                "principal_tenant": principal.tenant_id,
                "caller_tenant": extra["tenant_id"],
            },
        )
    filt = dict(extra)
    filt["tenant_id"] = principal.tenant_id
    return filt


def tenant_doc(principal: Principal, **fields: Any) -> dict[str, Any]:
    """Build an insert document with ``tenant_id`` locked to the principal."""
    if not principal.tenant_id:
        raise HTTPException(status_code=401, detail="Authenticated tenant required")
    doc = dict(fields)
    doc["tenant_id"] = principal.tenant_id
    return doc


__all__ = [
    "Principal",
    "get_principal",
    "get_principal_jwt_only",
    "tenant_filter",
    "tenant_doc",
]
