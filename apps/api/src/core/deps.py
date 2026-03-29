"""FastAPI dependency for accessing shared application state."""

from fastapi import Request

from src.core.dependencies import AgentDependencies


def get_deps(request: Request) -> AgentDependencies:
    """FastAPI dependency to access shared AgentDependencies from app.state.

    Used by routers to access the shared MongoDB connection and other
    dependencies initialized during app lifespan.
    """
    return request.app.state.deps
