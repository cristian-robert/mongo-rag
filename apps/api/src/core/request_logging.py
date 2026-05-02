"""Request logging middleware + sanitized exception handlers.

Attaches a request_id to every request, propagates it via response header,
and emits structured access logs. Never logs request bodies, query strings
verbatim (only path), or response payloads.

The middleware is **pure ASGI** — it implements ``async def __call__``
directly rather than subclassing ``BaseHTTPMiddleware``. The latter is
incompatible with ``StreamingResponse``/SSE because its ``receive``-channel
wrapper raises ``RuntimeError: Unexpected message received: http.request``
mid-stream (encode/starlette#1012, #1438). Pure ASGI passes ``receive`` /
``send`` straight through and is streaming-safe.
"""

from __future__ import annotations

import logging
import time
from typing import Awaitable, Callable

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.core.observability import (
    REQUEST_ID_HEADER,
    clear_request_context,
    new_request_id,
    set_request_context,
)

logger = logging.getLogger("mongorag.access")


class RequestLoggingMiddleware:
    """Per-request: assign request_id, log start/end with duration, scrub errors."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _extract_request_id(scope)

        # ContextVar-based logging context — works in pure ASGI because we
        # stay on the same task as the route handler (BaseHTTPMiddleware's
        # task group was the failure mode this middleware avoids).
        set_request_context(request_id=request_id)

        # Mirror BaseHTTPMiddleware's ``request.state.request_id = ...``
        # so handlers can read it via ``request.state.request_id``.
        state = scope.setdefault("state", {})
        state["request_id"] = request_id

        path: str = scope["path"]
        method: str = scope.get("method", "")
        request_id_bytes = request_id.encode("latin-1")
        lower_target = REQUEST_ID_HEADER.lower().encode("latin-1")

        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                # Always set X-Request-ID. Replace any existing value rather
                # than appending a duplicate header.
                headers = [
                    (n, v) for n, v in message.get("headers", []) if n.lower() != lower_target
                ]
                headers.append((lower_target, request_id_bytes))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            # Log and re-raise — Starlette's exception middleware (which is
            # outside ours via FastAPI's default stack) will produce the
            # framed 500 via ``install_exception_handlers``.
            duration_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "request_unhandled_exception",
                extra={
                    "method": method,
                    "path": path,
                    "duration_ms": round(duration_ms, 2),
                    "status_code": 500,
                },
            )
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            # Skip access logs for trivially noisy endpoints.
            if path not in ("/health", "/ready"):
                logger.info(
                    "request_complete",
                    extra={
                        "method": method,
                        "path": path,
                        "status_code": status_code,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
            clear_request_context()


def _extract_request_id(scope: Scope) -> str:
    """Pull the X-Request-ID from headers if present and safe; else mint one.

    Clamps client-supplied request_ids to a safe shape so log injection is
    impossible — UUIDs/hex only, max 64 chars.
    """
    needle = REQUEST_ID_HEADER.lower().encode("latin-1")
    incoming: str | None = None
    for raw_name, raw_value in scope.get("headers", []):
        if raw_name.lower() == needle:
            try:
                incoming = raw_value.decode("latin-1")
            except UnicodeDecodeError:
                incoming = None
            break

    if incoming and _is_safe_request_id(incoming):
        return incoming
    return new_request_id()


def _is_safe_request_id(value: str) -> bool:
    if not value or len(value) > 64:
        return False
    return all(c.isalnum() or c in "-_" for c in value)


def install_exception_handlers(app: FastAPI) -> None:
    """Register handlers that emit structured logs and sanitized responses.

    Clients never see stack traces, file paths, or internal exception types.
    """

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(  # type: ignore[unused-variable]
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning(
            "request_validation_failed",
            extra={"method": request.method, "path": request.url.path},
        )
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder({"detail": exc.errors(), "request_id": _rid(request)}),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(  # type: ignore[unused-variable]
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        # 5xx ⇒ log as error, 4xx ⇒ info (expected client errors).
        log_method: Callable[..., Awaitable[None]] | Callable[..., None] = (
            logger.error if exc.status_code >= 500 else logger.info
        )
        log_method(
            "http_exception",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": exc.status_code,
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "request_id": _rid(request)},
            headers=getattr(exc, "headers", None) or {},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(  # type: ignore[unused-variable]
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception(
            "unhandled_exception",
            extra={"method": request.method, "path": request.url.path},
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "request_id": _rid(request),
            },
        )


def _rid(request: Request) -> str:
    return getattr(request.state, "request_id", "") or ""
