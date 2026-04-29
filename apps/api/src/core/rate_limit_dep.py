"""FastAPI dependency wrappers for rate limiting and quota enforcement."""

import hashlib
import logging
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request

from src.core.dependencies import AgentDependencies
from src.core.deps import get_deps
from src.core.tenant import get_tenant_id
from src.models.usage import PlanLimits, QuotaExceededError
from src.services.rate_limit import get_default_limiter
from src.services.usage import UsageService

logger = logging.getLogger(__name__)


def _principal_key(authorization: Optional[str], tenant_id: str) -> str:
    """Derive a stable rate-limit key from the auth principal.

    Per-API-key rate limiting requires hashing the key (raw key has
    `mrag_` prefix; we never log it). For JWT sessions we fall back to
    tenant_id, which means dashboard traffic is rate-limited as a
    tenant aggregate.
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        if token.startswith("mrag_"):
            return "key:" + hashlib.sha256(token.encode()).hexdigest()[:32]
    return "tenant:" + tenant_id


def _client_ip(request: Request) -> str:
    """Best-effort client IP for unauthenticated rate limiting.

    Honours X-Forwarded-For only when the deployment terminates TLS at a
    trusted proxy (the proxy must strip client-set XFF). We take the
    left-most token because most proxies append.
    """
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


# Per-IP limit for unauthenticated endpoints (login/signup/forgot/reset).
# Tighter than per-tenant limits to slow brute-force credential attacks.
_AUTH_IP_LIMIT_PER_MINUTE = 20


async def enforce_auth_ip_rate_limit(request: Request) -> None:
    """Apply a per-IP rate limit to unauthenticated auth endpoints.

    Returns 429 with ``Retry-After`` when exceeded. Used on login,
    signup, forgot-password, reset-password — endpoints that do not yet
    have a tenant_id we could rate-limit by.
    """
    ip = _client_ip(request)
    limiter = get_default_limiter()
    key = "ip:" + ip
    result = await limiter.check(key, _AUTH_IP_LIMIT_PER_MINUTE, window_seconds=60)

    if not result.allowed:
        logger.warning(
            "auth_ip_rate_limited",
            extra={"ip_prefix": ip.rsplit(".", 1)[0] if "." in ip else ip[:6]},
        )
        raise HTTPException(
            status_code=429,
            detail="Too many requests — please retry shortly",
            headers={
                "Retry-After": str(result.reset_in),
                "X-RateLimit-Limit": str(result.limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(result.reset_in),
            },
        )


async def enforce_rate_limit(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    tenant_id: str = Depends(get_tenant_id),
    deps: AgentDependencies = Depends(get_deps),
) -> str:
    """Per-principal request rate limit. Returns tenant_id on success.

    Raises 429 with Retry-After header when the per-minute limit is
    exceeded. Limits are derived from the tenant's plan.
    """
    usage = UsageService(deps.usage_collection, deps.subscriptions_collection)
    plan = await usage.get_plan(tenant_id)
    limits = PlanLimits.for_plan(plan)

    key = _principal_key(authorization, tenant_id)
    limiter = get_default_limiter()
    result = await limiter.check(key, limits.requests_per_minute, window_seconds=60)

    # Attach headers to the response via state — middleware can apply them.
    request.state.rate_limit_headers = {
        "X-RateLimit-Limit": str(result.limit),
        "X-RateLimit-Remaining": str(result.remaining),
        "X-RateLimit-Reset": str(result.reset_in),
    }

    if not result.allowed:
        logger.warning(
            "rate_limit_exceeded",
            extra={"tenant_id": tenant_id, "limit": result.limit, "key_kind": key.split(":", 1)[0]},
        )
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={
                "Retry-After": str(result.reset_in),
                "X-RateLimit-Limit": str(result.limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(result.reset_in),
            },
        )

    return tenant_id


async def enforce_query_quota(
    tenant_id: str = Depends(enforce_rate_limit),
    deps: AgentDependencies = Depends(get_deps),
) -> str:
    """Reserve one chat query against the monthly quota.

    Chains after `enforce_rate_limit`. Returns 429 with Retry-After
    pointing to the period reset when the monthly cap is hit.
    """
    usage = UsageService(deps.usage_collection, deps.subscriptions_collection)
    try:
        await usage.check_query_quota(tenant_id)
    except QuotaExceededError as e:
        logger.info(
            "query_quota_exceeded",
            extra={"tenant_id": tenant_id, "used": e.used, "limit": e.limit},
        )
        raise HTTPException(
            status_code=429,
            detail=f"Monthly query quota exceeded ({e.used}/{e.limit})",
            headers={
                "Retry-After": str(e.retry_after or 3600),
                "X-Quota-Limit": str(e.limit),
                "X-Quota-Used": str(e.used),
            },
        )
    return tenant_id
