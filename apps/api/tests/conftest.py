"""Shared test fixtures."""

import os

# Set required env var defaults BEFORE any app imports trigger Settings loading
os.environ.setdefault("NEXTAUTH_SECRET", "test-secret-for-unit-tests-minimum-32chars")
os.environ.setdefault("RESEND_API_KEY", "re_test_placeholder")
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/test")
os.environ.setdefault("LLM_API_KEY", "test-llm-key")
os.environ.setdefault("EMBEDDING_API_KEY", "test-embedding-key")

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from jose import jwt

JWT_SECRET = "test-secret-for-unit-tests-minimum-32chars"

MOCK_TENANT_ID = "test-tenant-001"
MOCK_TENANT_B_ID = "test-tenant-002"


def make_auth_header(tenant_id: str = MOCK_TENANT_ID) -> dict:
    """Create Authorization header with JWT containing tenant_id."""
    token = jwt.encode(
        {"sub": "test-user", "tenant_id": tenant_id, "role": "owner"},
        JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def make_auth_header_b(tenant_id: str = MOCK_TENANT_B_ID) -> dict:
    """Create Authorization header for Tenant B."""
    token = jwt.encode(
        {"sub": "test-user-b", "tenant_id": tenant_id, "role": "owner"},
        JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


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
    deps.api_keys_collection = MagicMock()
    deps.ws_tickets_collection = MagicMock()
    deps.subscriptions_collection = MagicMock()
    deps.subscriptions_collection.find_one = AsyncMock(
        return_value={"plan": "free", "status": "active"}
    )
    deps.usage_collection = MagicMock()
    deps.usage_collection.find_one_and_update = AsyncMock(
        return_value={
            "tenant_id": MOCK_TENANT_ID,
            "period_key": "2026-04",
            "queries_count": 1,
        }
    )
    deps.usage_collection.update_one = AsyncMock()
    return deps


@pytest.fixture
def client(mock_deps):
    """Create test client with mocked dependencies via app.state."""
    from src.main import app

    with TestClient(app) as c:
        app.state.deps = mock_deps  # Override after lifespan runs
        yield c
