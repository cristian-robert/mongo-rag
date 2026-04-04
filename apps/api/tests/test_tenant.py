"""Tests for tenant dependency (JWT + API key auth)."""

import hashlib
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from tests.conftest import JWT_SECRET, MOCK_TENANT_ID


def _create_tenant_app():
    """Create a test app with tenant extraction."""
    from src.core.deps import get_deps
    from src.core.tenant import get_tenant_id

    app = FastAPI()

    @app.get("/test")
    async def test_endpoint(tenant_id: str = Depends(get_tenant_id)):
        return {"tenant_id": tenant_id}

    return app


@pytest.fixture
def tenant_app():
    """Create test client for JWT-only tests (no deps needed for JWT path)."""
    app = _create_tenant_app()
    # Set up mock deps on app.state so get_deps works
    mock_deps = MagicMock()
    mock_deps.api_keys_collection = MagicMock()
    mock_deps.api_keys_collection.find_one = AsyncMock(return_value=None)
    app.state.deps = mock_deps
    return TestClient(app)


@pytest.fixture
def api_key_app():
    """Create test client with mock api_keys collection for API key tests."""
    app = _create_tenant_app()
    mock_deps = MagicMock()
    mock_api_keys = MagicMock()
    mock_api_keys.find_one = AsyncMock(return_value=None)
    mock_api_keys.update_one = AsyncMock()
    mock_deps.api_keys_collection = mock_api_keys
    app.state.deps = mock_deps
    return TestClient(app), mock_api_keys


# --- JWT tests (unchanged behavior) ---


@pytest.mark.unit
def test_missing_auth_header_returns_401(tenant_app):
    """Request without Authorization header returns 401."""
    response = tenant_app.get("/test")
    assert response.status_code == 401
    assert "Authorization" in response.json()["detail"]


@pytest.mark.unit
def test_valid_jwt_returns_tenant_id(tenant_app):
    """Request with valid JWT extracts tenant_id."""
    token = jwt.encode(
        {"sub": "user-1", "tenant_id": MOCK_TENANT_ID, "role": "owner"},
        JWT_SECRET,
        algorithm="HS256",
    )
    response = tenant_app.get("/test", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["tenant_id"] == MOCK_TENANT_ID


@pytest.mark.unit
def test_invalid_jwt_returns_401(tenant_app):
    """Request with invalid JWT returns 401."""
    response = tenant_app.get("/test", headers={"Authorization": "Bearer bad-token"})
    assert response.status_code == 401


# --- API key tests ---


@pytest.mark.unit
def test_valid_api_key_returns_tenant_id(api_key_app):
    """Request with valid mrag_ API key extracts tenant_id."""
    client, mock_api_keys = api_key_app
    raw_key = "mrag_7kB2xR9mQ4nLpW5vX8yZ1aB3cD6eF9gH0jK2mN4"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    mock_api_keys.find_one.return_value = {
        "_id": "key-id-123",
        "tenant_id": "tenant-from-key",
        "key_hash": key_hash,
        "permissions": ["chat", "search"],
        "is_revoked": False,
    }

    response = client.get("/test", headers={"Authorization": f"Bearer {raw_key}"})
    assert response.status_code == 200
    assert response.json()["tenant_id"] == "tenant-from-key"

    # Verify last_used_at was updated
    mock_api_keys.update_one.assert_called_once()


@pytest.mark.unit
def test_revoked_api_key_returns_401(api_key_app):
    """Request with revoked API key returns 401."""
    client, mock_api_keys = api_key_app
    raw_key = "mrag_revokedkey12345678901234567890123"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    mock_api_keys.find_one.return_value = {
        "_id": "key-id-123",
        "tenant_id": "tenant-abc",
        "key_hash": key_hash,
        "permissions": ["chat"],
        "is_revoked": True,
    }

    response = client.get("/test", headers={"Authorization": f"Bearer {raw_key}"})
    assert response.status_code == 401
    assert "revoked" in response.json()["detail"].lower()


@pytest.mark.unit
def test_unknown_api_key_returns_401(api_key_app):
    """Request with unknown mrag_ key returns 401."""
    client, mock_api_keys = api_key_app
    mock_api_keys.find_one.return_value = None

    response = client.get(
        "/test", headers={"Authorization": "Bearer mrag_unknownkey123456789012345678"}
    )
    assert response.status_code == 401
    assert "Invalid API key" in response.json()["detail"]
