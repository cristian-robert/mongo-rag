"""HTTP middleware: tenant guard, security headers, body-size limits."""

import json
import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Routes exempt from tenant guard checks
_EXEMPT_PREFIXES = (
    "/api/v1/auth",
    "/api/v1/stripe",  # webhooks: signed by Stripe, no tenant JWT
    "/api/v1/billing/plans",  # public pricing catalog
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
)

# Path prefixes whose JSON bodies should NOT be scanned for ``tenant_id`` —
# typically multipart endpoints where streaming bodies are expensive to peek.
_TENANT_INPUT_BODY_EXEMPT_PREFIXES = (
    "/api/v1/documents/ingest",  # multipart upload
)

# Cap how many bytes of body we'll buffer when scanning for a forged
# ``tenant_id``. Bodies larger than this are passed through; the request
# is still safe because every Mongo query derives ``tenant_id`` from the
# authenticated Principal.
_TENANT_BODY_SCAN_LIMIT_BYTES = 1 * 1024 * 1024  # 1 MiB

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


class RejectClientTenantIdMiddleware(BaseHTTPMiddleware):
    """Reject any inbound request that tries to supply ``tenant_id`` itself.

    Tenant identity is derived server-side from the authenticated Principal.
    Any client-supplied ``tenant_id`` (in query string, path, or JSON body) is
    a strong signal of either a buggy client or an active cross-tenant attack.
    Rather than silently overriding it, we fail closed with HTTP 400 so the
    bug surfaces immediately.

    Defense in depth — even if a future code path forgot to use the
    ``tenant_filter()`` helper, this middleware ensures the only ``tenant_id``
    the handler can see is the authenticated one.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Path params are inspected as part of the URL. We refuse the literal
        # segment name ``tenant_id`` anywhere in the path, which catches
        # attempts to forge ``/api/v1/something/tenant_id/<id>``.
        path = request.url.path
        if "/tenant_id/" in path or path.endswith("/tenant_id"):
            return JSONResponse(
                status_code=400,
                content={"detail": "tenant_id is derived from auth — do not supply it"},
            )

        # Query string scan — cheap, runs first.
        if "tenant_id" in request.query_params:
            return JSONResponse(
                status_code=400,
                content={"detail": "tenant_id is derived from auth — do not supply it"},
            )

        # Body scan — only for JSON content types under the size cap, and
        # only on routes that actually accept JSON bodies. Multipart paths
        # are exempt to keep streaming uploads cheap.
        method = request.method.upper()
        if method in {"POST", "PUT", "PATCH"}:
            content_type = (request.headers.get("content-type") or "").split(";", 1)[0].strip()
            if content_type == "application/json" and not any(
                path.startswith(p) for p in _TENANT_INPUT_BODY_EXEMPT_PREFIXES
            ):
                content_length = request.headers.get("content-length")
                try:
                    declared_size = int(content_length) if content_length is not None else None
                except ValueError:
                    declared_size = None

                if declared_size is None or declared_size <= _TENANT_BODY_SCAN_LIMIT_BYTES:
                    body = await request.body()
                    if body and len(body) <= _TENANT_BODY_SCAN_LIMIT_BYTES:
                        if _body_mentions_tenant_id(body):
                            return JSONResponse(
                                status_code=400,
                                content={
                                    "detail": (
                                        "tenant_id is derived from auth — "
                                        "do not include it in the request body"
                                    )
                                },
                            )

                    # Re-attach the consumed body so downstream handlers see it.
                    async def _replay() -> dict:
                        return {"type": "http.request", "body": body, "more_body": False}

                    request._receive = _replay  # type: ignore[attr-defined]

        return await call_next(request)


def _body_mentions_tenant_id(body: bytes) -> bool:
    """Best-effort detection of a top-level ``tenant_id`` field in a JSON body.

    We parse instead of regex-matching to avoid false positives on, e.g., a
    user-uploaded document whose text happens to contain the string
    ``tenant_id``. JSON parse failures are treated as "not present" — Pydantic
    will reject the malformed body anyway.
    """
    try:
        parsed = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return False
    return _contains_tenant_id_key(parsed)


def _contains_tenant_id_key(value: object, depth: int = 0) -> bool:
    """Return True if any nested dict has a ``tenant_id`` key.

    Bounded recursion (max depth 5) to avoid pathological payloads.
    """
    if depth > 5:
        return False
    if isinstance(value, dict):
        if "tenant_id" in value:
            return True
        return any(_contains_tenant_id_key(v, depth + 1) for v in value.values())
    if isinstance(value, list):
        return any(_contains_tenant_id_key(v, depth + 1) for v in value)
    return False


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
