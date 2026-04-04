"""Tenant guard middleware -- safety net for missing tenant context."""

import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Routes exempt from tenant guard checks
_EXEMPT_PREFIXES = (
    "/api/v1/auth",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
)


class TenantGuardMiddleware(BaseHTTPMiddleware):
    """Log a warning if a protected route completes without tenant context.

    This is a safety net, not primary enforcement. Primary enforcement
    is the get_tenant_id() dependency injected into route handlers.

    Never blocks requests -- observability only.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Initialize tenant_id state so hasattr checks work
        request.state.tenant_id = None

        response = await call_next(request)

        path = request.url.path

        # Skip exempt routes
        if any(path.startswith(prefix) for prefix in _EXEMPT_PREFIXES):
            return response

        # Only check /api/v1/ routes
        if not path.startswith("/api/v1/"):
            return response

        # Only warn on successful responses — 401/403 are expected when
        # auth fails, and warning on those creates noise.
        if response.status_code >= 400:
            return response

        # Check if tenant context was set
        tenant_id = getattr(request.state, "tenant_id", None)
        if not tenant_id:
            logger.warning(
                "tenant_id not set for protected route",
                extra={"path": path, "method": request.method},
            )

        return response
