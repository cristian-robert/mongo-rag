"""Tests for API keys router endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from tests.conftest import make_auth_header


@pytest.fixture
def keys_client(mock_deps):
    """Create test client with api_keys collection mock."""
    from src.main import app

    mock_deps.api_keys_collection = MagicMock()

    with TestClient(app) as c:
        app.state.deps = mock_deps
        yield c


@pytest.mark.unit
def test_create_key_success(keys_client):
    """POST /api/v1/keys returns 201 with raw key."""
    with patch("src.routers.keys.APIKeyService") as mock_service:
        instance = mock_service.return_value
        instance.create_key = AsyncMock(
            return_value={
                "raw_key": "mrag_7kB2xR9mQ4nLpW5vX8yZ1aB3cD6eF9gH0jK2mN4",
                "key_prefix": "7kB2xR9m",
                "name": "Production",
                "permissions": ["chat", "search"],
                "created_at": datetime(2026, 4, 4, tzinfo=timezone.utc),
            }
        )

        response = keys_client.post(
            "/api/v1/keys",
            json={"name": "Production"},
            headers=make_auth_header(),
        )

    assert response.status_code == 201
    data = response.json()
    assert data["raw_key"].startswith("mrag_")
    assert data["key_prefix"] == "7kB2xR9m"
    assert data["name"] == "Production"


@pytest.mark.unit
def test_create_key_without_auth_returns_401(keys_client):
    """POST /api/v1/keys without auth returns 401."""
    response = keys_client.post(
        "/api/v1/keys",
        json={"name": "Test Key"},
    )
    assert response.status_code == 401


@pytest.mark.unit
def test_list_keys_success(keys_client):
    """GET /api/v1/keys returns key list for tenant."""
    key_id = str(ObjectId())
    with patch("src.routers.keys.APIKeyService") as mock_service:
        instance = mock_service.return_value
        instance.list_keys = AsyncMock(
            return_value=[
                {
                    "id": key_id,
                    "key_prefix": "7kB2xR9m",
                    "name": "Production",
                    "permissions": ["chat", "search"],
                    "is_revoked": False,
                    "last_used_at": None,
                    "created_at": datetime(2026, 4, 4, tzinfo=timezone.utc),
                }
            ]
        )

        response = keys_client.get(
            "/api/v1/keys",
            headers=make_auth_header(),
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data["keys"]) == 1
    assert data["keys"][0]["key_prefix"] == "7kB2xR9m"
    assert "key_hash" not in data["keys"][0]


@pytest.mark.unit
def test_list_keys_empty(keys_client):
    """GET /api/v1/keys returns empty list for tenant with no keys."""
    with patch("src.routers.keys.APIKeyService") as mock_service:
        instance = mock_service.return_value
        instance.list_keys = AsyncMock(return_value=[])

        response = keys_client.get(
            "/api/v1/keys",
            headers=make_auth_header(),
        )

    assert response.status_code == 200
    assert response.json()["keys"] == []


@pytest.mark.unit
def test_revoke_key_success(keys_client):
    """DELETE /api/v1/keys/{key_id} revokes the key."""
    key_id = str(ObjectId())
    with patch("src.routers.keys.APIKeyService") as mock_service:
        instance = mock_service.return_value
        instance.revoke_key = AsyncMock(return_value=True)

        response = keys_client.delete(
            f"/api/v1/keys/{key_id}",
            headers=make_auth_header(),
        )

    assert response.status_code == 200
    assert "revoked" in response.json()["message"].lower()


@pytest.mark.unit
def test_revoke_key_not_found(keys_client):
    """DELETE /api/v1/keys/{key_id} returns 404 for wrong tenant or missing key."""
    key_id = str(ObjectId())
    with patch("src.routers.keys.APIKeyService") as mock_service:
        instance = mock_service.return_value
        instance.revoke_key = AsyncMock(return_value=False)

        response = keys_client.delete(
            f"/api/v1/keys/{key_id}",
            headers=make_auth_header(),
        )

    assert response.status_code == 404


@pytest.mark.unit
def test_revoke_key_invalid_id_format(keys_client):
    """DELETE /api/v1/keys/{key_id} returns 400 for invalid ObjectId."""
    with patch("src.routers.keys.APIKeyService") as mock_service:
        instance = mock_service.return_value
        instance.revoke_key = AsyncMock(side_effect=Exception("invalid ObjectId"))

        response = keys_client.delete(
            "/api/v1/keys/not-a-valid-id",
            headers=make_auth_header(),
        )

    assert response.status_code == 400
