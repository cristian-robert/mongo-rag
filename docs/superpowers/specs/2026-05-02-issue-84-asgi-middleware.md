# Issue #84 — Pure-ASGI middleware translation

## Problem

All five custom backend middlewares subclass Starlette's `BaseHTTPMiddleware`. That base class wraps the ASGI `receive` channel in its own task group so it can materialize a `Request` and pass it to `dispatch()`. When a route returns a `StreamingResponse` (e.g. SSE on `POST /api/v1/chat`), Starlette's response code reads `receive()` again to listen for client disconnect. The wrapper sees an `http.request` it isn't prepared for and raises `RuntimeError: Unexpected message received: http.request` mid-stream — the SSE tears down before the client finishes reading.

Reference: encode/starlette#1012, #1438, discussion #1739.

## Fix shape

Each middleware becomes a pure ASGI class:

```python
class FooMiddleware:
    def __init__(self, app: ASGIApp, *, ...) -> None:
        self.app = app
        ...

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        # ... pre-work using scope (path, method, headers) ...
        await self.app(scope, receive_wrapper_or_receive, send_wrapper_or_send)
        # ... post-work via captured state in send_wrapper ...
```

Key rules:
- ASGI types: `from starlette.types import ASGIApp, Message, Receive, Scope, Send`
- `scope["type"] != "http"` → pass through untouched (websocket, lifespan)
- Headers in ASGI are a `list[tuple[bytes, bytes]]` — must be bytes, lowercase keys
- To emit a 4xx/5xx response without rebuilding ASGI framing, instantiate a Starlette `Response(...)` and call `await response(scope, receive, send)`
- Headers added in a `send_wrapper` must be set on the `http.response.start` message before delegating: `message["headers"].append((b"x-key", b"value"))` (or replace via dict→list rebuild)

## Per-middleware translation

### 1. `RejectClientTenantIdMiddleware` — simplest, no body in current pure logic except for JSON scan

Current behavior:
- Reject if path contains `/tenant_id/` segment
- Reject if `tenant_id` is in query string
- For JSON `POST/PUT/PATCH` (not on `_TENANT_INPUT_BODY_EXEMPT_PREFIXES`), peek the body up to 1 MiB; if it parses as JSON and contains a `tenant_id` key (top-level or nested up to depth 5), reject 400.
- After body peek, replay the consumed body via `request._receive`.

ASGI translation:
- Read `scope["path"]`, `scope["query_string"]`, `scope["method"]` directly.
- For JSON body scan: read all `http.request` messages until `more_body == False`, accumulate `body` bytes (cap-aware). Then `_body_mentions_tenant_id(body)`. If clean, fabricate a single replay `receive()` that returns the buffered body once, then `{"type": "http.disconnect"}` afterwards.
- 400 rejection: `await Response(content=json_str, status_code=400, media_type="application/json")(scope, receive, send)`.
- For routes whose content-type isn't JSON or method doesn't carry a body: pass through `receive` directly.

Edge cases:
- `Content-Length` header parsed via `scope["headers"]` (bytes). Must lowercase the header name to compare.
- Declared size > 1 MiB → skip the scan, pass through (matches current behavior).
- Body actually larger than 1 MiB despite missing/wrong Content-Length → still safe because Pydantic + the `_TENANT_BODY_SCAN_LIMIT_BYTES` cap is best-effort; if we exceed, we abandon the scan and pass the (already buffered) body through replay.

### 2. `TenantGuardMiddleware` — observability-only

Current behavior:
- Sets `request.state.tenant_id = None` initially.
- After response, if path is non-exempt, status < 400, and `request.state.tenant_id` was never set → log warning.

ASGI translation:
- We can't easily mutate `request.state` from outside FastAPI's `Request` lifecycle. But Starlette stores state on `scope["state"]` (added to scope by FastAPI). Setting `scope.setdefault("state", {})["tenant_id"] = None` is equivalent to the current `request.state.tenant_id = None`.
- We need the response status before logging — capture in a `send_wrapper` via `http.response.start`.
- After `await self.app(...)`, read `scope["state"].get("tenant_id")`. The route handler has had an opportunity to write to it via `request.state.tenant_id = ...`, which becomes `scope["state"]["tenant_id"]`.
- Skip exempt prefixes; only check `/api/v1/`; skip if status >= 400.

Note: FastAPI initializes `scope["state"]` on each request — we don't need to create it. Reading via `scope.get("state", {}).get("tenant_id")` is safe. Still, write `tenant_id = None` defensively the same way the BaseHTTPMiddleware version did. This is equivalent and preserves the `hasattr` semantics for downstream code.

### 3. `SecurityHeadersMiddleware` — header injection on response start

Current behavior:
- Use `headers.setdefault(...)` to attach 6+ baseline security headers + `Cache-Control: no-store` + (in prod) `Strict-Transport-Security`.
- `setdefault` semantics: don't overwrite headers the route already set (e.g. SSE's `Cache-Control: no-cache`).

ASGI translation:
- Wrap `send`. On `http.response.start`, mutate `message["headers"]` (list of `(name_bytes, value_bytes)` tuples).
- Implement `setdefault` over a list of tuples by lowercasing names: build a `seen = {name_lower for name, _ in headers}`, then append only if not in `seen`.
- All header names/values must be `bytes` — encode ASCII.

### 4. `BodySizeLimitMiddleware` — Content-Length fast reject

Current behavior:
- If path is in `_BODY_SIZE_EXEMPT_PREFIXES`, pass through.
- Else read `Content-Length`. If non-numeric → 400. If > limit → 413. Otherwise pass through.

ASGI translation:
- Pure header inspection on `scope["headers"]`. No body wrapping needed (existing code only uses `Content-Length` header — it doesn't enforce against actual streamed bytes). Send the 400/413 via `Response(...)(scope, receive, send)`.

The issue notes "wrap `receive` to count `http.request` body bytes and raise / 413 once the cap is exceeded" as the most thorough form, but the **current** code only does Content-Length checks — preserving existing behavior is the goal (per AC: "body-size limit enforced with 413"). Keeping it simple and matching the existing tests in `test_security_hardening.py`. Will note this in the plan.

### 5. `RequestLoggingMiddleware` — request_id, access log, status capture

Current behavior:
- Read `X-Request-ID` from request, validate shape (alnum+`-_`, ≤64 chars), else mint new.
- Set `set_request_context(request_id=...)` and `request.state.request_id = request_id` so log emitter and downstream code see it.
- Time the request. After response: set `X-Request-ID` response header, log `request_complete` with method/path/status_code/duration_ms (skipping `/health` and `/ready`).
- On exception: log `request_unhandled_exception` and re-raise so `install_exception_handlers` can format the sanitized 500.

ASGI translation:
- `set_request_context(...)` and `clear_request_context()` use a contextvar — these must be called in the same async task as the route handler. Pure ASGI keeps us on the same task by default (no `BaseHTTPMiddleware` task group), so this works naturally.
- `request.state.request_id = request_id` becomes `scope.setdefault("state", {})["request_id"] = request_id`. (FastAPI exposes this as `request.state.request_id` to handlers.)
- Wrap `send`. On `http.response.start`:
  - Capture `status_code = message["status"]` for the access log.
  - Append `(b"x-request-id", request_id.encode())` to `message["headers"]` (we always want it; current code uses raw assignment, not setdefault — preserve that; if the route somehow already set it, we'll have duplicate header which is fine for `X-Request-ID`, or we replace).
- Default `status_code = 500` so an exception that prevents `http.response.start` still logs as 500.
- Skip access log for `/health` and `/ready`. Always `clear_request_context()` in `finally`.
- Exception path: catch in `__call__`, log `request_unhandled_exception` with `logger.exception(...)`, re-raise. Starlette's `ServerErrorMiddleware` (added by FastAPI by default) will emit the framed 500 — but we still need our `install_exception_handlers` to scrub the body. **Important:** when we re-raise out of pure ASGI, the FastAPI exception handler (registered via `@app.exception_handler(Exception)`) is what handles it — that hook is wired through Starlette's exception middleware which sits inside the routing layer, so by the time our middleware catches, the exception handler has already produced a clean 500 response. Re-check this.

  Actually: FastAPI exception handlers run inside `Router`/`Route`. If they catch and return a response, we never see the exception in middleware. We see the exception only if the handler chain failed too. So the `try/except/raise` block keeps the same semantics: sanity log only on truly unhandled cases.

  But — preserving "default status_code = 500 in finally if start never sent" still applies, since the handler converting an exception to a 500 is what would emit `http.response.start` with status=500. So `send_wrapper` captures it normally.

### Order in `main.py`

Comment block in `main.py` documents the desired order:
```
CORS -> RequestLogging -> SecurityHeaders -> BodySizeLimit -> RejectClientTenantId -> TenantGuard -> route
```
(Starlette adds in reverse, so registration order in `_configure_middleware` stays the same.)

## Test strategy

### Unit tests (per-middleware)

For each middleware, exercise pure-ASGI behavior using FastAPI `TestClient` against a tiny app that mounts only that middleware:

- `RequestLoggingMiddleware`:
  - assigns request_id header on response (`tests/test_observability.py` already covers this — should keep passing post-translation)
  - propagates client-supplied request_id (already covered)
  - rejects unsafe request_id and mints new (already covered)
  - sanitized 500 path (already covered)

- `SecurityHeadersMiddleware`:
  - all baseline headers present (already covered)
  - HSTS only in prod (already covered)
  - **NEW:** does NOT overwrite headers the route already set (e.g. `Cache-Control: no-cache` from SSE) — add explicit test to lock down `setdefault` semantics in pure ASGI

- `BodySizeLimitMiddleware`:
  - 413 on oversize Content-Length (covered)
  - 400 on invalid Content-Length (covered)
  - small payload allowed (covered)
  - exempt paths bypassed (covered)

- `RejectClientTenantIdMiddleware`: existing tests in `tests/test_reject_client_tenant_id_middleware.py` should keep passing.

- `TenantGuardMiddleware`: existing tests in `tests/test_tenant_guard.py` should keep passing.

### Integration test (NEW — the smoking gun)

`tests/integration/test_chat_sse_middleware.py` (or unit-marked equivalent if Mongo not required):

Build a tiny FastAPI app with **all five custom middlewares mounted in production order** plus a single SSE route that yields N events. POST it with `Accept: text/event-stream`, stream-read the response, assert all events were received and no exception in the captured logs.

We don't need MongoDB to reproduce the bug — the bug is purely in the middleware/streaming interaction. So this can be a **unit-marked** test for fast feedback. We'll mark it `unit` and put it next to the other middleware tests.

Plus: add a regression test that pre-translation would have caught the original bug. The simplest form is: mount all five middlewares around a `StreamingResponse` route, POST and consume the stream. Pre-fix, this raises `RuntimeError: Unexpected message received: http.request`. Post-fix, the stream completes cleanly.

## Per-middleware send_wrapper / receive_wrapper helpers

Common pattern factored locally (no shared helpers beyond per-file convenience — KISS, YAGNI):

```python
async def send_wrapper(message: Message) -> None:
    nonlocal status_code  # for RequestLogging
    if message["type"] == "http.response.start":
        status_code = message["status"]
        # mutate message["headers"] for SecurityHeaders / RequestLogging
    await send(message)
```

Replay `receive` for RejectClientTenantId only:

```python
sent = False
async def replay_receive() -> Message:
    nonlocal sent
    if not sent:
        sent = True
        return {"type": "http.request", "body": buffered_body, "more_body": False}
    return await receive()  # forward subsequent (e.g. http.disconnect)
```

## Order of execution (TDD)

Start with `RejectClientTenantIdMiddleware` — most complex (has body replay) but has a complete existing test suite to lock down. If we keep that suite green AND add a streaming integration test that exercises it, we lock down the trickiest pattern first.

Then `BodySizeLimitMiddleware` (simplest, header-only), then `SecurityHeadersMiddleware` (send_wrapper for headers), then `RequestLoggingMiddleware` (send_wrapper + state mutation), and finally `TenantGuardMiddleware` (state read after route).

The integration test goes last to verify the whole stack.
