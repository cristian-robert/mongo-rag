"""FastAPI application factory."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.database import ensure_indexes
from src.core.dependencies import AgentDependencies
from src.core.middleware import TenantGuardMiddleware
from src.core.observability import configure_logging, init_sentry
from src.core.request_logging import RequestLoggingMiddleware, install_exception_handlers
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

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3100"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tenant guard middleware (safety net -- logs warnings, never blocks)
app.add_middleware(TenantGuardMiddleware)

# Request logging middleware — must be added LAST so it runs FIRST (Starlette
# wraps middleware in reverse-add order). This guarantees every request, even
# those rejected by tenant guard / CORS, gets a request_id + access log.
app.add_middleware(RequestLoggingMiddleware)

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
