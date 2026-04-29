"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.database import ensure_indexes
from src.core.dependencies import AgentDependencies
from src.core.middleware import TenantGuardMiddleware
from src.routers.auth import router as auth_router
from src.routers.billing import router as billing_router
from src.routers.bots import router as bots_router
from src.routers.chat import router as chat_router
from src.routers.health import router as health_router
from src.routers.ingest import router as ingest_router
from src.routers.keys import router as keys_router
from src.routers.usage import router as usage_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and clean up application resources."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger.info("Starting MongoRAG API...")
    deps = AgentDependencies()
    try:
        await deps.initialize()
        app.state.deps = deps
    except Exception as e:
        logger.error("Failed to initialize: %s", e)
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
    logger.info("MongoRAG API started successfully")
    yield
    logger.info("Shutting down MongoRAG API...")
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

# Include routers
app.include_router(health_router)
app.include_router(ingest_router)
app.include_router(chat_router)
app.include_router(auth_router)
app.include_router(keys_router)
app.include_router(usage_router)
app.include_router(billing_router)
app.include_router(bots_router)
