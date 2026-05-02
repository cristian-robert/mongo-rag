# Plan — Issue #84: pure ASGI middleware to unblock SSE

## Goal

Convert all five custom backend middlewares from `BaseHTTPMiddleware` subclasses to pure ASGI classes so `StreamingResponse` (notably the SSE chat endpoint) consumes cleanly without `RuntimeError: Unexpected message received: http.request`.

## Mandatory reading

Before starting:
- `apps/api/src/core/middleware.py` — current home of 4 middlewares to convert
- `apps/api/src/core/request_logging.py` — current home of 5th middleware
- `apps/api/src/main.py` — middleware registration order (lines 99-160)
- `apps/api/src/routers/chat.py` lines 22-58 — the SSE route this is meant to unblock
- `apps/api/tests/test_security_hardening.py` — existing tests; must keep green
- `apps/api/tests/test_observability.py` — existing RequestLoggingMiddleware tests
- `apps/api/tests/test_reject_client_tenant_id_middleware.py` — existing tests
- `apps/api/tests/test_tenant_guard.py` — existing tests
- The design notes: `docs/superpowers/specs/2026-05-02-issue-84-asgi-middleware.md`

External:
- Starlette pure-ASGI docs: https://www.starlette.io/middleware/#writing-pure-asgi-middleware
- Starlette `Response.__call__` source: https://github.com/encode/starlette/blob/master/starlette/responses.py — confirms calling `await response(scope, receive, send)` is the supported way to emit a fully-framed response from ASGI middleware
- Issue thread: https://github.com/encode/starlette/issues/1438

## Verification commands

Run from `apps/api/`:

```bash
# Lint
uv run ruff check .

# Format check (scoped to changed files)
git diff --name-only main...HEAD | grep '\.py$' | xargs uv run ruff format --check

# Unit tests (deselect pre-existing audit failure tracked in #101)
uv run pytest -m unit -q --deselect tests/test_tenant_filter_audit.py::test_every_mongo_call_in_apps_api_is_tenant_scoped

# Integration tests (require MongoDB)
uv run pytest -m integration -q --deselect tests/test_tenant_filter_audit.py::test_every_mongo_call_in_apps_api_is_tenant_scoped

# Targeted middleware suites (fast iteration during dev)
uv run pytest -q tests/test_reject_client_tenant_id_middleware.py tests/test_tenant_guard.py tests/test_security_hardening.py tests/test_observability.py tests/test_chat_sse_middleware_stack.py
```

## Tasks (TDD ordering)

### Task 1 — Add streaming-stack regression test (RED)

Create `apps/api/tests/test_chat_sse_middleware_stack.py`. Mount **all five custom middlewares plus CORS** in production order around a tiny FastAPI app with one SSE route that yields, say, 5 `data: ...\n\n` chunks. POST with `Accept: text/event-stream`, stream-read the response with `TestClient`'s streaming API, assert:
- HTTP 200
- All 5 events arrive intact
- No `RuntimeError` and no log line containing `Unexpected message received` (capture via caplog at ERROR level)
- Response `X-Request-ID` header present
- Security headers present (`X-Content-Type-Options`)
- Response `Cache-Control` is `no-cache` (route's own, not overwritten by middleware's `no-store`)

**This test fails on `main` today**. Mark `@pytest.mark.unit` (no Mongo needed). Commit as a failing test that documents the bug.

`/commit` slash command. Conventional message: `test(api): failing SSE-through-middleware-stack regression for #84`.

### Task 2 — Convert RejectClientTenantIdMiddleware (GREEN for existing tests, partial green for Task 1)

In `apps/api/src/core/middleware.py`:

- Remove `BaseHTTPMiddleware` import (replace with `from starlette.types import ASGIApp, Message, Receive, Scope, Send`)
- Rewrite `RejectClientTenantIdMiddleware` as pure ASGI per spec
- Reuse the existing `_body_mentions_tenant_id` and `_contains_tenant_id_key` helpers unchanged
- Use `Response(...)(scope, receive, send)` for 400 rejections
- Use the replay-receive pattern for the body peek

Run `uv run pytest -q tests/test_reject_client_tenant_id_middleware.py` — must be green.

`/commit`: `refactor(api): convert RejectClientTenantIdMiddleware to pure ASGI (#84)`

### Task 3 — Convert BodySizeLimitMiddleware

In `apps/api/src/core/middleware.py`: rewrite per spec. Header-only inspection, `Response(...)` for 400/413.

Run `uv run pytest -q tests/test_security_hardening.py` — must be green.

`/commit`: `refactor(api): convert BodySizeLimitMiddleware to pure ASGI (#84)`

### Task 4 — Convert SecurityHeadersMiddleware

In `apps/api/src/core/middleware.py`: rewrite using a `send_wrapper` that mutates `http.response.start` headers list. Implement `setdefault`-equivalent logic on a `list[tuple[bytes, bytes]]` by collecting existing lowercase header names into a set first.

Add a NEW test in `test_security_hardening.py`:
```python
def test_security_headers_does_not_override_route_cache_control():
    """SSE routes set Cache-Control: no-cache; middleware must not clobber it."""
```

Run `uv run pytest -q tests/test_security_hardening.py` — must be green.

`/commit`: `refactor(api): convert SecurityHeadersMiddleware to pure ASGI (#84)`

### Task 5 — Convert TenantGuardMiddleware

In `apps/api/src/core/middleware.py`: rewrite. Read `scope["state"]` after `await self.app(...)` (FastAPI populates it; we tolerate it being missing). Capture status via `send_wrapper`.

Run `uv run pytest -q tests/test_tenant_guard.py` — must be green.

`/commit`: `refactor(api): convert TenantGuardMiddleware to pure ASGI (#84)`

### Task 6 — Convert RequestLoggingMiddleware

In `apps/api/src/core/request_logging.py`: rewrite. Replace `BaseHTTPMiddleware` import with ASGI types. Preserve:
- request_id generation/validation logic (`_is_safe_request_id` unchanged)
- `set_request_context` / `clear_request_context` calls (still work in same task)
- `scope["state"]["request_id"]` write so `request.state.request_id = ...` semantics are preserved
- access log on `/health`/`/ready` skip
- exception path

`install_exception_handlers` is unchanged — still hooks via `@app.exception_handler`.

Run `uv run pytest -q tests/test_observability.py` — must be green.

`/commit`: `refactor(api): convert RequestLoggingMiddleware to pure ASGI (closes #84)`

### Task 7 — Re-run the regression test from Task 1 (final GREEN)

Run `uv run pytest -q tests/test_chat_sse_middleware_stack.py` — must now be green.

If `main.py` needs any registration tweaks (it shouldn't — same constructor signatures preserved), apply them in the same commit.

`/commit`: `test(api): SSE-through-middleware-stack regression now passes (#84)` — only if any code/test tweak was needed; if the regression test passes without further changes, skip this commit.

### Task 8 — Final lint + format check (scoped)

```bash
uv run ruff check .
git diff --name-only main...HEAD | grep '\.py$' | xargs uv run ruff format --check
```

Both must be clean against the diff. No extra commit unless ruff finds something in the diff.

## Verification gates (Phase 4)

In order:
1. `uv run ruff check .` — clean
2. `git diff --name-only main...HEAD | grep '\.py$' | xargs uv run ruff format --check` — clean against diff
3. `uv run pytest -m unit -q --deselect tests/test_tenant_filter_audit.py::test_every_mongo_call_in_apps_api_is_tenant_scoped` — green
4. `uv run pytest -m integration -q --deselect tests/test_tenant_filter_audit.py::test_every_mongo_call_in_apps_api_is_tenant_scoped` — green (Mongo-backed; skip if not reachable, document in PR)
5. Manual SSE smoke (optional, only if api boots quickly)

## "No prior knowledge" walkthrough

A fresh agent reading only this plan must be able to:
- Find the five middleware classes (paths listed in Mandatory reading)
- Know what each is supposed to do (read the existing dispatch() methods and the spec doc)
- Know the pure-ASGI translation pattern (see spec doc)
- Know how to test (commands listed under Verification)
- Know the gotcha to avoid (`BaseHTTPMiddleware` + `StreamingResponse` is the bug; `Response(...)(scope, receive, send)` is the supported escape hatch for early rejection)

## Out of scope

- `CORSMiddleware` — Starlette built-in, already pure ASGI
- The widget (`packages/widget/src/auth.ts` JSON workaround stays per user instruction; #86 will revert)
- `webhook_delivery.py:176` tenant audit failure (tracked in #101, deselected for this PR)
- The four pre-existing ruff-format-misses on main; we don't touch those files

## Commit log preview

```
test(api): failing SSE-through-middleware-stack regression for #84
refactor(api): convert RejectClientTenantIdMiddleware to pure ASGI (#84)
refactor(api): convert BodySizeLimitMiddleware to pure ASGI (#84)
refactor(api): convert SecurityHeadersMiddleware to pure ASGI (#84)
refactor(api): convert TenantGuardMiddleware to pure ASGI (#84)
refactor(api): convert RequestLoggingMiddleware to pure ASGI (closes #84)
```
