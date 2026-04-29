"""FastAPI application factory."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.database import ensure_indexes
from src.core.dependencies import AgentDependencies
from src.core.middleware import (
    BodySizeLimitMiddleware,
    SecurityHeadersMiddleware,
    TenantGuardMiddleware,
)
from src.core.observability import configure_logging, init_sentry
from src.core.request_logging import RequestLoggingMiddleware, install_exception_handlers
from src.core.settings import load_settings
from src.routers.auth import router as auth_router
from src.routers.billing import router as billing_router
from src.routers.bots import router as bots_router
from src.routers.chat import router as chat_router
from src.routers.documents import router as documents_router
from src.routers.health import router as health_router
from src.routers.ingest import router as ingest_router
from src.routers.keys import router as keys_router
from src.routers.usage import router as usage_router

# Install structured JSON logging before any module-level logger acquires
# a handler from the default config.
configure_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    service="mongorag-api",
)

# Best-effort Sentry init — graceful no-op when DSN unset or SDK missing.
init_sentry(
    dsn=os.getenv("SENTRY_DSN"),
    environment=os.getenv("APP_ENV", "development"),
    release=os.getenv("SENTRY_RELEASE"),
    traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and clean up application resources."""
    logger.info("api_starting")
    deps = AgentDependencies()
    try:
        await deps.initialize()
        app.state.deps = deps
    except Exception as e:
        logger.error("api_initialize_failed", extra={"error": str(e)})
        app.state.deps = deps  # Store even on failure so health can report it
        yield
        return

    # Index creation is separate — failure is fatal because tenant
    # isolation guarantees depend on these indexes (e.g. unique email).
    try:
        await ensure_indexes(deps.db, deps.settings)
    except Exception:
        await deps.cleanup()
        raise
    logger.info("api_started")
    yield
    logger.info("api_shutting_down")
    await deps.cleanup()


app = FastAPI(
    title="MongoRAG API",
    description="Multi-tenant RAG backend powered by MongoDB Atlas Vector Search",
    version="0.1.0",
    lifespan=lifespan,
)


def _configure_middleware(application: FastAPI) -> None:
    """Wire security middleware in the right order.

    Order matters — Starlette runs middleware in reverse-add order, so the
    last added is outermost. We want, on the way in:
        CORS -> RequestLogging -> SecurityHeaders -> BodySizeLimit ->
        TenantGuard -> route
    """
    settings = load_settings()

    origins = settings.cors_origins_list
    if not origins:
        # Fail closed: an empty allow-list means no browser may call us.
        # In production this is the right default rather than `*`.
        origins = []

    if settings.is_production and ("*" in origins or any(o.strip() == "*" for o in origins)):
        raise RuntimeError("CORS_ALLOWED_ORIGINS must not contain '*' in production")

    # Tenant guard runs closest to the handler (added first → innermost).
    application.add_middleware(TenantGuardMiddleware)

    # Body-size limit before tenant guard to reject oversized payloads
    # before any business logic runs.
    application.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_request_body_bytes)

    # Security headers wrap the business response.
    application.add_middleware(SecurityHeadersMiddleware, is_production=settings.is_production)

    # Request logging sits just inside CORS so every request — even those
    # rejected by tenant guard or body-size — gets a request_id and access
    # log entry. Adding it here (after security headers) means it runs
    # BEFORE them on the way in (Starlette reverses add order).
    application.add_middleware(RequestLoggingMiddleware)

    # CORS is the outermost layer — it must see preflight OPTIONS and
    # apply Access-Control headers even on error responses.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Accept",
            "X-Requested-With",
        ],
        expose_headers=[
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ],
        max_age=600,
    )


_configure_middleware(app)

# Sanitized exception handlers — never leak stack traces to clients.
install_exception_handlers(app)

# Include routers
app.include_router(health_router)
app.include_router(ingest_router)
# documents_router shares the /api/v1/documents prefix with ingest_router but
# owns the CRUD verbs; registered after so its dynamic /{id} routes don't
# shadow the literal /ingest path on the ingest router.
app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(auth_router)
app.include_router(keys_router)
app.include_router(usage_router)
app.include_router(billing_router)
app.include_router(bots_router)
