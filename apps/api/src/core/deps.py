"""FastAPI dependency for accessing shared application state."""

from typing import Optional

import asyncpg
from fastapi import Request

from src.core.dependencies import AgentDependencies


def get_deps(request: Request) -> AgentDependencies:
    """FastAPI dependency to access shared AgentDependencies from app.state.

    Used by routers to access the shared MongoDB connection and other
    dependencies initialized during app lifespan.
    """
    return request.app.state.deps


def get_pg_pool(request: Request) -> Optional[asyncpg.Pool]:
    """Optional asyncpg pool for Postgres-backed API key validation (#42).

    Returns ``None`` when DATABASE_URL is not configured — callers must
    handle that case (e.g. fall back to Mongo or fail closed).
    """
    return getattr(request.app.state, "pg_pool", None)
