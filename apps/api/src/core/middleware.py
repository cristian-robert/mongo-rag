"""HTTP middleware: tenant guard, security headers, body-size limits."""

import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Routes exempt from tenant guard checks
_EXEMPT_PREFIXES = (
    "/api/v1/auth",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
)

# Endpoints that legitimately accept large bodies (file uploads).
# Body-size limiting for these is enforced inside the handler using the
# tenant's plan-aware max_upload_size_mb setting.
_BODY_SIZE_EXEMPT_PREFIXES = (
    "/api/v1/documents/ingest",
    "/api/v1/documents/",  # reingest variants stream multipart bodies
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


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach baseline security response headers to every response.

    The dashboard CSP lives in the Next.js layer (next.config.ts). Here we
    set the Helmet-equivalent baseline that protects API responses from
    being reflected/embedded by malicious origins.
    """

    def __init__(self, app, *, is_production: bool = False) -> None:
        super().__init__(app)
        self._is_production = is_production

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        headers = response.headers

        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), payment=()",
        )
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        headers.setdefault("Cross-Origin-Resource-Policy", "same-site")

        # API responses should never be cached by intermediaries by default.
        # Individual handlers (e.g. SSE) override Cache-Control intentionally.
        headers.setdefault("Cache-Control", "no-store")

        if self._is_production:
            headers.setdefault(
                "Strict-Transport-Security",
                "max-age=63072000; includeSubDomains; preload",
            )

        return response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests that exceed the configured maximum body size.

    Uses the Content-Length header for fast rejection. Multipart upload
    endpoints are exempt — they enforce their own per-plan size limit
    after streaming the body to disk.
    """

    def __init__(self, app, *, max_bytes: int) -> None:
        super().__init__(app)
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if any(path.startswith(p) for p in _BODY_SIZE_EXEMPT_PREFIXES):
            return await call_next(request)

        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                size = int(content_length)
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header"},
                )
            if size > self._max_bytes:
                logger.warning(
                    "request_body_too_large",
                    extra={"path": path, "size": size, "limit": self._max_bytes},
                )
                return JSONResponse(
                    status_code=413,
                    content={"detail": (f"Request body too large (max {self._max_bytes} bytes)")},
                )

        return await call_next(request)
