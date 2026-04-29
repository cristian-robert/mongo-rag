"""Observability primitives — structured JSON logging, request context, Sentry init.

Single module so callers do not need to know whether structlog or Sentry is
installed. All knobs are environment-driven via Pydantic Settings; missing
optional deps degrade gracefully.

Design notes:
- Stdlib-only logging with a custom JSON formatter. Avoids adding structlog
  to the dependency surface for this issue.
- Per-request context (request_id, tenant_id, user_id) lives in a contextvar
  and is merged into every log record automatically.
- Secret/PII redaction happens in the formatter so callers can not bypass it
  by forgetting to scrub.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Any, Mapping, Optional

# Per-request context — set by middleware, read by formatter.
_request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_tenant_id_var: ContextVar[Optional[str]] = ContextVar("tenant_id", default=None)
_user_id_var: ContextVar[Optional[str]] = ContextVar("user_id", default=None)

# Header name used end-to-end for correlation.
REQUEST_ID_HEADER = "x-request-id"

# Field names that must never appear in logs as raw values.
_SENSITIVE_KEY_PATTERN = re.compile(
    r"(?i)(password|passwd|secret|token|api[_-]?key|authorization|cookie|session|"
    r"stripe|webhook|signing|bearer|client[_-]?secret|private[_-]?key)"
)

# Patterns that look like high-entropy secrets even if the field name is benign.
_SECRET_VALUE_PATTERNS = [
    re.compile(r"sk_(?:live|test)_[A-Za-z0-9]{16,}"),  # Stripe secret
    re.compile(r"whsec_[A-Za-z0-9]{16,}"),  # Stripe webhook secret
    re.compile(r"sb_(?:secret|publishable)_[A-Za-z0-9]{16,}"),  # Supabase
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE),  # Bearer tokens
    re.compile(r"eyJ[A-Za-z0-9._\-]{20,}"),  # JWT-ish
]

_REDACTED = "[REDACTED]"

# Standard LogRecord attributes — anything else is treated as user-extra.
_RESERVED_LOGRECORD_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "message",
    "module",
    "msecs",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}


def set_request_context(
    request_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> None:
    """Set per-request context. Pass None to leave a field unchanged."""
    if request_id is not None:
        _request_id_var.set(request_id)
    if tenant_id is not None:
        _tenant_id_var.set(tenant_id)
    if user_id is not None:
        _user_id_var.set(user_id)


def clear_request_context() -> None:
    """Reset all context vars — call at request teardown."""
    _request_id_var.set(None)
    _tenant_id_var.set(None)
    _user_id_var.set(None)


def get_request_id() -> Optional[str]:
    return _request_id_var.get()


def new_request_id() -> str:
    """Mint a fresh request_id (UUID4 hex, no dashes)."""
    return uuid.uuid4().hex


def _redact_value(value: Any) -> Any:
    """Recursively redact secret-looking strings inside a value."""
    if isinstance(value, str):
        scrubbed = value
        for pattern in _SECRET_VALUE_PATTERNS:
            scrubbed = pattern.sub(_REDACTED, scrubbed)
        return scrubbed
    if isinstance(value, Mapping):
        return {k: _redact_field(k, v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact_value(v) for v in value]
    return value


def _redact_field(key: str, value: Any) -> Any:
    """Redact based on field name first, then on value patterns."""
    if isinstance(key, str) and _SENSITIVE_KEY_PATTERN.search(key):
        return _REDACTED
    return _redact_value(value)


class JsonFormatter(logging.Formatter):
    """Render LogRecord as one-line JSON, merging request context + extras."""

    def __init__(self, service: str = "mongorag-api") -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "service": self.service,
            "message": record.getMessage(),
        }

        request_id = _request_id_var.get()
        tenant_id = _tenant_id_var.get()
        user_id = _user_id_var.get()
        if request_id:
            payload["request_id"] = request_id
        if tenant_id:
            payload["tenant_id"] = tenant_id
        if user_id:
            payload["user_id"] = user_id

        # Merge structured extras (anything passed via logger.info(..., extra={...}))
        for key, value in record.__dict__.items():
            if key in _RESERVED_LOGRECORD_ATTRS or key.startswith("_"):
                continue
            payload[key] = _redact_field(key, value)

        if record.exc_info:
            # Use formatException — never include locals or full chain payloads.
            payload["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            payload["exc_message"] = str(record.exc_info[1]) if record.exc_info[1] else None
            # Stack trace stays server-side only; clients never see this string.
            payload["stack"] = self.formatException(record.exc_info)

        try:
            return json.dumps(payload, default=str, ensure_ascii=False)
        except (TypeError, ValueError):
            # Last-ditch fallback — never let a logging call raise.
            return json.dumps(
                {
                    "ts": payload["ts"],
                    "level": payload["level"],
                    "logger": payload["logger"],
                    "message": payload["message"],
                    "service": self.service,
                    "log_serialization_failed": True,
                }
            )


def configure_logging(
    level: str = "INFO",
    service: str = "mongorag-api",
    *,
    force: bool = True,
) -> None:
    """Install the JSON formatter on the root logger.

    Idempotent — safe to call multiple times.
    """
    root = logging.getLogger()
    if force:
        for handler in list(root.handlers):
            root.removeHandler(handler)

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JsonFormatter(service=service))
    root.addHandler(handler)

    try:
        root.setLevel(getattr(logging, level.upper()))
    except AttributeError:
        root.setLevel(logging.INFO)

    # Tame chatty libraries.
    for noisy in ("uvicorn.access", "pymongo", "httpx", "openai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def init_sentry(
    dsn: Optional[str],
    environment: str = "development",
    release: Optional[str] = None,
    traces_sample_rate: float = 0.0,
    profiles_sample_rate: float = 0.0,
) -> bool:
    """Initialize Sentry if a DSN is configured and the SDK is installed.

    Returns True on success, False on graceful no-op.
    """
    if not dsn:
        return False
    try:
        import sentry_sdk  # type: ignore[import-not-found]
        from sentry_sdk.integrations.fastapi import FastApiIntegration  # type: ignore
        from sentry_sdk.integrations.starlette import StarletteIntegration  # type: ignore
    except ImportError:
        logging.getLogger(__name__).warning(
            "sentry_dsn_set_but_sdk_missing",
            extra={"hint": "pip install sentry-sdk[fastapi]"},
        )
        return False

    def _before_send(event: dict, _hint: dict) -> Optional[dict]:
        # Strip request body / cookies / headers that could carry secrets.
        request = event.get("request") or {}
        request.pop("data", None)
        request.pop("cookies", None)
        headers = request.get("headers") or {}
        if isinstance(headers, dict):
            request["headers"] = {
                k: (_REDACTED if _SENSITIVE_KEY_PATTERN.search(k) else v)
                for k, v in headers.items()
            }
        event["request"] = request
        # Recursively scrub any extra payload strings.
        if "extra" in event and isinstance(event["extra"], dict):
            event["extra"] = {k: _redact_field(k, v) for k, v in event["extra"].items()}
        return event

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        traces_sample_rate=traces_sample_rate,
        profiles_sample_rate=profiles_sample_rate,
        send_default_pii=False,  # Never send IPs / cookies / auth headers.
        before_send=_before_send,
        integrations=[FastApiIntegration(), StarletteIntegration()],
    )
    return True


def sentry_configured() -> bool:
    """Cheap probe — True only if `sentry_sdk` is installed AND a DSN is set."""
    if not os.getenv("SENTRY_DSN"):
        return False
    try:
        import sentry_sdk  # type: ignore[import-not-found]

        return sentry_sdk.Hub.current.client is not None
    except Exception:  # noqa: BLE001
        return False
