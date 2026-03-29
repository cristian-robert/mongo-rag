"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.dependencies import AgentDependencies
from src.routers.chat import router as chat_router
from src.routers.health import router as health_router
from src.routers.ingest import router as ingest_router

logger = logging.getLogger(__name__)

# Shared dependencies instance for app lifecycle
_deps = AgentDependencies()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and clean up application resources."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger.info("Starting MongoRAG API...")
    try:
        await _deps.initialize()
        logger.info("MongoRAG API started successfully")
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        # Don't crash — health endpoint will report the failure
    yield
    logger.info("Shutting down MongoRAG API...")
    await _deps.cleanup()


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

# Include routers
app.include_router(health_router)
app.include_router(ingest_router)
app.include_router(chat_router)
