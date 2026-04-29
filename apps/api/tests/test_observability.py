"""Tests for structured logging, redaction, request context, and middleware."""

from __future__ import annotations

import io
import json
import logging

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.core.observability import (
    REQUEST_ID_HEADER,
    JsonFormatter,
    clear_request_context,
    configure_logging,
    new_request_id,
    set_request_context,
)
from src.core.request_logging import (
    RequestLoggingMiddleware,
    install_exception_handlers,
)

# ---------- JsonFormatter ----------


def _format_record(logger_name: str, msg: str, **extra) -> dict:
    """Render a single log record through JsonFormatter and parse the JSON."""
    formatter = JsonFormatter(service="test-service")
    record = logging.LogRecord(
        name=logger_name,
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )
    for k, v in extra.items():
        setattr(record, k, v)
    return json.loads(formatter.format(record))


@pytest.mark.unit
def test_formatter_emits_json_with_required_fields():
    payload = _format_record("foo", "hello")
    assert payload["level"] == "INFO"
    assert payload["logger"] == "foo"
    assert payload["service"] == "test-service"
    assert payload["message"] == "hello"
    assert "ts" in payload


@pytest.mark.unit
def test_formatter_redacts_sensitive_field_names():
    payload = _format_record(
        "auth",
        "login",
        password="hunter2",
        api_key="mrag_live_abc123abc123",
        Authorization="Bearer eyJabc",
    )
    assert payload["password"] == "[REDACTED]"
    assert payload["api_key"] == "[REDACTED]"
    assert payload["Authorization"] == "[REDACTED]"


@pytest.mark.unit
def test_formatter_redacts_secret_value_patterns_even_in_innocent_fields():
    payload = _format_record(
        "stripe",
        "charge",
        note="see sk_live_abcdefghij1234567890 and whsec_zzzzzzzzzzzz1234",
    )
    assert "sk_live_" not in payload["note"]
    assert "whsec_" not in payload["note"]
    assert "[REDACTED]" in payload["note"]


@pytest.mark.unit
def test_formatter_redacts_jwt_like_strings():
    payload = _format_record(
        "auth",
        "session",
        body="cookie: eyJhbGciOiJIUzI1NiJ9.payloadpartcontent.signaturepart",
    )
    assert "[REDACTED]" in payload["body"]


@pytest.mark.unit
def test_formatter_redacts_nested_dicts():
    payload = _format_record(
        "billing",
        "webhook",
        context={"user": {"password": "hunter2", "name": "Alice"}},
    )
    assert payload["context"]["user"]["password"] == "[REDACTED]"
    assert payload["context"]["user"]["name"] == "Alice"


@pytest.mark.unit
def test_formatter_includes_request_context_when_set():
    set_request_context(request_id="abc123", tenant_id="tenant-1", user_id="u1")
    try:
        payload = _format_record("svc", "doing thing")
        assert payload["request_id"] == "abc123"
        assert payload["tenant_id"] == "tenant-1"
        assert payload["user_id"] == "u1"
    finally:
        clear_request_context()


@pytest.mark.unit
def test_formatter_omits_unset_context_fields():
    clear_request_context()
    payload = _format_record("svc", "no context")
    assert "request_id" not in payload
    assert "tenant_id" not in payload


@pytest.mark.unit
def test_formatter_renders_exception_without_locals():
    formatter = JsonFormatter()
    try:
        raise ValueError("boom secret_key=sk_live_abc123abc123abc123")
    except ValueError:
        import sys

        record = logging.LogRecord(
            name="x",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="failed",
            args=(),
            exc_info=sys.exc_info(),
        )
    payload = json.loads(formatter.format(record))
    assert payload["exc_type"] == "ValueError"
    # The exception MESSAGE itself isn't redacted (it's a Python-side string),
    # but the formatter shouldn't crash and stack trace should be present.
    assert "stack" in payload


# ---------- configure_logging ----------


@pytest.mark.unit
def test_configure_logging_installs_json_formatter():
    buffer = io.StringIO()
    configure_logging(level="INFO", service="t")
    # Replace the stream so we can capture output
    root = logging.getLogger()
    handler = root.handlers[0]
    handler.stream = buffer

    logging.getLogger("test").info("hello", extra={"foo": "bar"})

    output = buffer.getvalue().strip()
    parsed = json.loads(output)
    assert parsed["message"] == "hello"
    assert parsed["foo"] == "bar"


# ---------- Middleware integration ----------


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)
    install_exception_handlers(app)

    @app.get("/ok")
    async def ok() -> dict:
        return {"ok": True}

    @app.get("/boom")
    async def boom() -> dict:
        raise RuntimeError("internal-detail-do-not-leak")

    @app.get("/forbidden")
    async def forbidden() -> dict:
        raise HTTPException(status_code=403, detail="nope")

    return app


@pytest.mark.unit
def test_middleware_attaches_request_id_header():
    client = TestClient(_make_app())
    resp = client.get("/ok")
    assert resp.status_code == 200
    assert resp.headers.get(REQUEST_ID_HEADER)


@pytest.mark.unit
def test_middleware_propagates_client_request_id():
    client = TestClient(_make_app())
    resp = client.get("/ok", headers={REQUEST_ID_HEADER: "abc123def456"})
    assert resp.headers[REQUEST_ID_HEADER] == "abc123def456"


@pytest.mark.unit
def test_middleware_rejects_unsafe_request_id_and_mints_new():
    client = TestClient(_make_app())
    bad = "value with spaces\nand newlines and = signs"
    resp = client.get("/ok", headers={REQUEST_ID_HEADER: bad})
    assert resp.headers[REQUEST_ID_HEADER] != bad
    assert resp.headers[REQUEST_ID_HEADER]


@pytest.mark.unit
def test_unhandled_exception_returns_sanitized_500():
    client = TestClient(_make_app(), raise_server_exceptions=False)
    resp = client.get("/boom")
    assert resp.status_code == 500
    body = resp.json()
    assert body["detail"] == "Internal server error"
    # Internal exception text MUST NOT appear in the client response
    assert "internal-detail-do-not-leak" not in resp.text
    assert "RuntimeError" not in resp.text
    assert body["request_id"]


@pytest.mark.unit
def test_http_exception_preserves_detail_and_adds_request_id():
    client = TestClient(_make_app())
    resp = client.get("/forbidden")
    assert resp.status_code == 403
    body = resp.json()
    assert body["detail"] == "nope"
    assert body["request_id"]


@pytest.mark.unit
def test_new_request_id_is_unique():
    a = new_request_id()
    b = new_request_id()
    assert a != b
    assert len(a) == 32
