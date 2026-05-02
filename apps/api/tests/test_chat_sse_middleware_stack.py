"""Regression: SSE / StreamingResponse must consume cleanly through the full
middleware stack.

Pre-fix (issue #84) all five custom middlewares subclass
``BaseHTTPMiddleware``. That base class's ``receive``-channel wrapping is
incompatible with ``StreamingResponse`` (Starlette issues #1012, #1438) —
the response tears mid-stream with
``RuntimeError: Unexpected message received: http.request``.

This test mounts the production middleware stack (minus auth bits, which
are orthogonal) around a tiny SSE route and asserts the stream consumes
cleanly with no error log.
"""

from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from src.core.middleware import (
    BodySizeLimitMiddleware,
    RejectClientTenantIdMiddleware,
    SecurityHeadersMiddleware,
    TenantGuardMiddleware,
)
from src.core.observability import REQUEST_ID_HEADER
from src.core.request_logging import RequestLoggingMiddleware


def _build_app() -> FastAPI:
    """Build a tiny app with the production middleware stack and one SSE route."""
    app = FastAPI()

    @app.post("/api/v1/sse-echo")
    async def sse_echo(request: Request) -> StreamingResponse:
        async def gen():
            for i in range(5):
                yield f"data: chunk-{i}\n\n"

        # Mark tenant context so TenantGuardMiddleware stays silent.
        request.state.tenant_id = "test-tenant"
        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Register in the same order as src/main.py::_configure_middleware.
    # Starlette runs add_middleware in reverse — first added is innermost.
    app.add_middleware(TenantGuardMiddleware)
    app.add_middleware(RejectClientTenantIdMiddleware)
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=1_048_576)
    app.add_middleware(SecurityHeadersMiddleware, is_production=False)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3101"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
        max_age=600,
    )
    return app


@pytest.mark.unit
def test_sse_streams_cleanly_through_middleware_stack(caplog) -> None:
    """The SSE response must complete with all chunks and no middleware errors."""
    app = _build_app()
    client = TestClient(app)

    with caplog.at_level(logging.ERROR):
        with client.stream(
            "POST",
            "/api/v1/sse-echo",
            json={"message": "hi"},
            headers={"Accept": "text/event-stream"},
        ) as r:
            assert r.status_code == 200
            body = b"".join(r.iter_bytes())

    # All 5 chunks delivered.
    decoded = body.decode("utf-8")
    for i in range(5):
        assert f"data: chunk-{i}" in decoded, f"missing chunk-{i} in stream"

    # No "Unexpected message received" anywhere — the canonical symptom of
    # the BaseHTTPMiddleware + StreamingResponse incompatibility.
    error_log = "\n".join(
        rec.getMessage() + " " + str(rec.exc_info or "") for rec in caplog.records
    )
    assert "Unexpected message received" not in error_log, (
        f"BaseHTTPMiddleware bug regressed:\n{error_log}"
    )


@pytest.mark.unit
def test_sse_response_carries_request_id_and_security_headers() -> None:
    """Streaming responses still get RequestLogging + SecurityHeaders treatment."""
    app = _build_app()
    client = TestClient(app)

    with client.stream(
        "POST",
        "/api/v1/sse-echo",
        json={"message": "hi"},
        headers={"Accept": "text/event-stream"},
    ) as r:
        assert r.status_code == 200
        # RequestLoggingMiddleware always sets X-Request-ID.
        assert r.headers.get(REQUEST_ID_HEADER), "RequestLoggingMiddleware did not set X-Request-ID"
        # SecurityHeadersMiddleware always sets the baseline.
        assert r.headers.get("X-Content-Type-Options") == "nosniff"
        # SecurityHeadersMiddleware uses setdefault — must NOT clobber the
        # route's own Cache-Control on SSE.
        assert r.headers.get("Cache-Control") == "no-cache"

        # Drain the body so the connection closes cleanly.
        for _ in r.iter_bytes():
            pass


@pytest.mark.unit
def test_non_streaming_json_path_still_works() -> None:
    """Regression guard — JSON responses unaffected by the middleware rewrite."""
    app = _build_app()

    @app.post("/api/v1/json-echo")
    async def json_echo(request: Request) -> dict:
        request.state.tenant_id = "test-tenant"
        return {"ok": True}

    client = TestClient(app)
    r = client.post("/api/v1/json-echo", json={"message": "hi"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
