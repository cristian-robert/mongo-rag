"""Tests for API keys router endpoints (Postgres-backed, #42).

The router talks to ``src.auth.api_keys``; we patch those module-level
async functions and override the ``get_pg_pool`` dep with a sentinel so
the ``_require_pool`` guard passes.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.core.deps import get_pg_pool
from tests.conftest import make_auth_header


@pytest.fixture
def keys_client(mock_deps):
    """Test client with the Postgres pool dependency stubbed out."""
    from src.main import app

    mock_deps.api_keys_collection = MagicMock()
    fake_pool = MagicMock(name="pg_pool_sentinel")
    app.dependency_overrides[get_pg_pool] = lambda: fake_pool

    with TestClient(app) as c:
        app.state.deps = mock_deps
        yield c

    app.dependency_overrides.pop(get_pg_pool, None)


@pytest.mark.unit
def test_create_key_success(keys_client):
    with patch("src.routers.keys.pg_api_keys.create_key", new_callable=AsyncMock) as create:
        create.return_value = {
            "id": str(uuid4()),
            "raw_key": "mrag_7kB2xR9mQ4nLpW5vX8yZ1aB3cD6eF9gH0jK2mN4",
            "key_prefix": "7kB2xR9m",
            "name": "Production",
            "created_at": datetime(2026, 4, 4, tzinfo=timezone.utc),
        }

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
    assert data["permissions"] == ["chat", "search"]


@pytest.mark.unit
def test_create_key_without_auth_returns_401(keys_client):
    response = keys_client.post("/api/v1/keys", json={"name": "Test Key"})
    assert response.status_code == 401


@pytest.mark.unit
def test_create_key_with_api_key_returns_403(keys_client):
    response = keys_client.post(
        "/api/v1/keys",
        json={"name": "Test Key"},
        headers={"Authorization": "Bearer mrag_someapikey12345678901234567890"},
    )
    assert response.status_code == 403
    assert "API keys cannot access this endpoint" in response.json()["detail"]


@pytest.mark.unit
def test_list_keys_success(keys_client):
    key_id = str(uuid4())
    with patch("src.routers.keys.pg_api_keys.list_keys", new_callable=AsyncMock) as listfn:
        listfn.return_value = [
            {
                "id": key_id,
                "key_prefix": "7kB2xR9m",
                "name": "Production",
                "is_revoked": False,
                "last_used_at": None,
                "created_at": datetime(2026, 4, 4, tzinfo=timezone.utc),
            }
        ]
        response = keys_client.get("/api/v1/keys", headers=make_auth_header())

    assert response.status_code == 200
    data = response.json()
    assert len(data["keys"]) == 1
    assert data["keys"][0]["key_prefix"] == "7kB2xR9m"
    # Hashes / secrets must never appear in list responses
    assert "key_hash" not in data["keys"][0]
    assert "raw_key" not in data["keys"][0]


@pytest.mark.unit
def test_list_keys_empty(keys_client):
    with patch("src.routers.keys.pg_api_keys.list_keys", new_callable=AsyncMock) as listfn:
        listfn.return_value = []
        response = keys_client.get("/api/v1/keys", headers=make_auth_header())

    assert response.status_code == 200
    assert response.json()["keys"] == []


@pytest.mark.unit
def test_revoke_key_success(keys_client):
    key_id = str(uuid4())
    with patch("src.routers.keys.pg_api_keys.revoke_key", new_callable=AsyncMock) as revoke:
        revoke.return_value = True
        response = keys_client.delete(f"/api/v1/keys/{key_id}", headers=make_auth_header())

    assert response.status_code == 200
    assert "revoked" in response.json()["message"].lower()


@pytest.mark.unit
def test_revoke_key_not_found(keys_client):
    key_id = str(uuid4())
    with patch("src.routers.keys.pg_api_keys.revoke_key", new_callable=AsyncMock) as revoke:
        revoke.return_value = False
        response = keys_client.delete(f"/api/v1/keys/{key_id}", headers=make_auth_header())

    assert response.status_code == 404


@pytest.mark.unit
def test_revoke_key_invalid_id_format(keys_client):
    with patch("src.routers.keys.pg_api_keys.revoke_key", new_callable=AsyncMock) as revoke:
        revoke.side_effect = ValueError("invalid uuid")
        response = keys_client.delete("/api/v1/keys/not-a-valid-id", headers=make_auth_header())

    assert response.status_code == 400
