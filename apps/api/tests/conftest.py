"""Shared test fixtures."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_deps():
    """Create mock AgentDependencies."""
    deps = MagicMock()
    deps.initialize = AsyncMock()
    deps.cleanup = AsyncMock()
    deps.db = MagicMock()
    deps.settings = MagicMock()
    deps.tenants_collection = MagicMock()
    deps.documents_collection = MagicMock()
    deps.chunks_collection = MagicMock()
    deps.conversations_collection = MagicMock()
    return deps


@pytest.fixture
def client(mock_deps):
    """Create test client with mocked dependencies via app.state."""
    from src.main import app

    with TestClient(app) as c:
        app.state.deps = mock_deps  # Override after lifespan runs
        yield c


MOCK_TENANT_ID = "test-tenant-001"
