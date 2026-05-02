"""HTTP middleware: tenant guard, security headers, body-size limits.

All middlewares in this module are **pure ASGI** — they implement
``async def __call__(scope, receive, send)`` directly rather than
subclassing ``starlette.middleware.base.BaseHTTPMiddleware``. The latter
is incompatible with ``StreamingResponse``/SSE: its ``receive``-channel
wrapper raises ``RuntimeError: Unexpected message received: http.request``
mid-stream when the streaming response code calls ``receive()`` to listen
for client disconnect (encode/starlette#1012, #1438). Pure ASGI passes
``receive``/``send`` straight through and is fully streaming-safe.
"""

import json
import logging

from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

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


def _header_value(scope: Scope, name: str) -> str | None:
    """Return the first matching header value from an ASGI scope, or None.

    Header names are matched case-insensitively (ASGI guarantees lowercase keys
    on incoming requests, but we lower() defensively).
    """
    needle = name.lower().encode("latin-1")
    for raw_name, raw_value in scope.get("headers", []):
        if raw_name.lower() == needle:
            try:
                return raw_value.decode("latin-1")
            except UnicodeDecodeError:
                return None
    return None


def _query_params(scope: Scope) -> dict[str, list[str]]:
    """Parse the query string from an ASGI scope into a dict."""
    from urllib.parse import parse_qs

    raw = scope.get("query_string", b"")
    if not raw:
        return {}
    return parse_qs(raw.decode("latin-1"), keep_blank_values=True)


class TenantGuardMiddleware:
    """Log a warning if a protected route completes without tenant context.

    This is a safety net, not primary enforcement. Primary enforcement
    is the get_tenant_id() dependency injected into route handlers.

    Never blocks requests -- observability only.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Initialize tenant_id state so handlers/downstream see a known key.
        # FastAPI populates ``scope["state"]`` per request and exposes it as
        # ``request.state``; setting it here mirrors the BaseHTTPMiddleware
        # version's ``request.state.tenant_id = None`` behavior.
        state = scope.setdefault("state", {})
        state.setdefault("tenant_id", None)

        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            path: str = scope["path"]

            # Skip exempt routes
            if any(path.startswith(prefix) for prefix in _EXEMPT_PREFIXES):
                return

            # Only check /api/v1/ routes
            if not path.startswith("/api/v1/"):
                return

            # Only warn on successful responses — 401/403 are expected when
            # auth fails, and warning on those creates noise.
            if status_code >= 400:
                return

            # Check if tenant context was set
            tenant_id = scope.get("state", {}).get("tenant_id")
            if not tenant_id:
                logger.warning(
                    "tenant_id not set for protected route",
                    extra={"path": path, "method": scope.get("method", "")},
                )


class SecurityHeadersMiddleware:
    """Attach baseline security response headers to every response.

    The dashboard CSP lives in the Next.js layer (next.config.ts). Here we
    set the Helmet-equivalent baseline that protects API responses from
    being reflected/embedded by malicious origins.
    """

    # Static defaults applied to every response. Order doesn't matter — we
    # use setdefault semantics, so if the route already set a value (e.g.
    # SSE's ``Cache-Control: no-cache``) we leave it alone.
    _DEFAULT_HEADERS: tuple[tuple[bytes, bytes], ...] = (
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"referrer-policy", b"strict-origin-when-cross-origin"),
        (
            b"permissions-policy",
            b"geolocation=(), microphone=(), camera=(), payment=()",
        ),
        (b"cross-origin-opener-policy", b"same-origin"),
        (b"cross-origin-resource-policy", b"same-site"),
        # API responses should never be cached by intermediaries by default.
        # Individual handlers (e.g. SSE) override Cache-Control intentionally.
        (b"cache-control", b"no-store"),
    )
    _HSTS_HEADER: tuple[bytes, bytes] = (
        b"strict-transport-security",
        b"max-age=63072000; includeSubDomains; preload",
    )

    def __init__(self, app: ASGIApp, *, is_production: bool = False) -> None:
        self.app = app
        self._is_production = is_production

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                # Lowercase-name set so we don't overwrite headers the route
                # already produced (setdefault semantics).
                seen = {name.lower() for name, _ in headers}
                for name, value in self._DEFAULT_HEADERS:
                    if name not in seen:
                        headers.append((name, value))
                        seen.add(name)
                if self._is_production and self._HSTS_HEADER[0] not in seen:
                    headers.append(self._HSTS_HEADER)
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


class RejectClientTenantIdMiddleware:
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

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope["path"]

        # Path params are inspected as part of the URL. We refuse the literal
        # segment name ``tenant_id`` anywhere in the path, which catches
        # attempts to forge ``/api/v1/something/tenant_id/<id>``.
        if "/tenant_id/" in path or path.endswith("/tenant_id"):
            await _reject_tenant_id(
                scope, send, "tenant_id is derived from auth — do not supply it"
            )
            return

        # Query string scan — cheap, runs first.
        if "tenant_id" in _query_params(scope):
            await _reject_tenant_id(
                scope, send, "tenant_id is derived from auth — do not supply it"
            )
            return

        # Body scan — only for JSON content types under the size cap, and
        # only on routes that actually accept JSON bodies. Multipart paths
        # are exempt to keep streaming uploads cheap.
        method = scope.get("method", "").upper()
        if method in {"POST", "PUT", "PATCH"}:
            content_type_raw = _header_value(scope, "content-type") or ""
            content_type = content_type_raw.split(";", 1)[0].strip()
            if content_type == "application/json" and not any(
                path.startswith(p) for p in _TENANT_INPUT_BODY_EXEMPT_PREFIXES
            ):
                content_length_raw = _header_value(scope, "content-length")
                try:
                    declared_size = (
                        int(content_length_raw) if content_length_raw is not None else None
                    )
                except ValueError:
                    declared_size = None

                if declared_size is None or declared_size <= _TENANT_BODY_SCAN_LIMIT_BYTES:
                    body = await _read_body(receive, _TENANT_BODY_SCAN_LIMIT_BYTES)
                    if body is not None and _body_mentions_tenant_id(body):
                        await _reject_tenant_id(
                            scope,
                            send,
                            (
                                "tenant_id is derived from auth — "
                                "do not include it in the request body"
                            ),
                        )
                        return

                    # Re-attach the buffered body so downstream sees it.
                    receive = _make_replay_receive(body or b"", original_receive=receive)

        await self.app(scope, receive, send)


async def _reject_tenant_id(scope: Scope, send: Send, detail: str) -> None:
    """Emit a JSON 400 response framed by Starlette's ``Response``."""
    body = json.dumps({"detail": detail}).encode("utf-8")
    # ``Response.__call__`` only uses ``scope["type"]`` and ``send``. Pass
    # the real scope so any future Starlette enhancement (e.g. HEAD-method
    # body suppression) works without a behavior change here.
    await Response(content=body, status_code=400, media_type="application/json")(
        scope,
        _no_op_receive,
        send,
    )


async def _no_op_receive() -> Message:
    """Receive replacement used when emitting a fixed response.

    Returning ``http.disconnect`` ends any wait if Starlette's response code
    listens for client disconnects.
    """
    return {"type": "http.disconnect"}


async def _read_body(receive: Receive, limit: int) -> bytes | None:
    """Drain the request body up to ``limit`` bytes.

    Returns the buffered bytes, or ``None`` if the body exceeds the limit
    (in which case the caller should pass the original receive through and
    skip the scan — matching the BaseHTTPMiddleware version's "too big to
    scan" behavior).
    """
    chunks: list[bytes] = []
    total = 0
    more_body = True
    while more_body:
        message = await receive()
        if message["type"] == "http.disconnect":
            # Client gave up before we finished — replay an empty body so the
            # downstream app can also observe the disconnect on its own
            # ``receive()``.
            return b"".join(chunks)
        if message["type"] != "http.request":
            # Non-request messages are unexpected here. Bail out gracefully.
            break
        chunk = message.get("body", b"") or b""
        total += len(chunk)
        if total > limit:
            return None
        chunks.append(chunk)
        more_body = message.get("more_body", False)
    return b"".join(chunks)


def _make_replay_receive(body: bytes, *, original_receive: Receive) -> Receive:
    """Build a ``receive`` callable that yields the buffered body once.

    Subsequent calls forward to ``original_receive`` (e.g. so client disconnect
    messages still propagate).
    """
    sent = False

    async def replay() -> Message:
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return await original_receive()

    return replay


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


class BodySizeLimitMiddleware:
    """Reject requests that exceed the configured maximum body size.

    Uses the Content-Length header for fast rejection. Multipart upload
    endpoints are exempt — they enforce their own per-plan size limit
    after streaming the body to disk.
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self.app = app
        self._max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope["path"]
        if any(path.startswith(p) for p in _BODY_SIZE_EXEMPT_PREFIXES):
            await self.app(scope, receive, send)
            return

        content_length_raw = _header_value(scope, "content-length")
        if content_length_raw is not None:
            try:
                size = int(content_length_raw)
            except ValueError:
                await _reject_simple(
                    scope, send, status=400, detail="Invalid Content-Length header"
                )
                return
            if size > self._max_bytes:
                logger.warning(
                    "request_body_too_large",
                    extra={"path": path, "size": size, "limit": self._max_bytes},
                )
                await _reject_simple(
                    scope,
                    send,
                    status=413,
                    detail=f"Request body too large (max {self._max_bytes} bytes)",
                )
                return

        await self.app(scope, receive, send)


async def _reject_simple(scope: Scope, send: Send, *, status: int, detail: str) -> None:
    """Emit a JSON error response with the given status."""
    body = json.dumps({"detail": detail}).encode("utf-8")
    await Response(content=body, status_code=status, media_type="application/json")(
        scope,
        _no_op_receive,
        send,
    )
