"""Request logging middleware + sanitized exception handlers.

Attaches a request_id to every request, propagates it via response header,
and emits structured access logs. Never logs request bodies, query strings
verbatim (only path), or response payloads.
"""

from __future__ import annotations

import logging
import time
from typing import Awaitable, Callable

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.core.observability import (
    REQUEST_ID_HEADER,
    clear_request_context,
    new_request_id,
    set_request_context,
)

logger = logging.getLogger("mongorag.access")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Per-request: assign request_id, log start/end with duration, scrub errors."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or new_request_id()
        # Clamp client-supplied request_ids to a safe shape so log injection is
        # impossible — UUIDs/hex only, max 64 chars.
        if not _is_safe_request_id(request_id):
            request_id = new_request_id()

        set_request_context(request_id=request_id)
        request.state.request_id = request_id

        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        except Exception:
            # Re-raise after logging — FastAPI's exception handler chain
            # will produce the sanitized response.
            duration_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "request_unhandled_exception",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duration_ms, 2),
                    "status_code": 500,
                },
            )
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            # Skip access logs for trivially noisy endpoints.
            if request.url.path not in ("/health", "/ready"):
                logger.info(
                    "request_complete",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": status_code,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
            clear_request_context()


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
            content={"detail": exc.errors(), "request_id": _rid(request)},
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
