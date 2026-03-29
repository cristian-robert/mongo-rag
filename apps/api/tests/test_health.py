"""Tests for health check endpoint."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client with mocked dependencies."""
    with patch("src.main._deps") as mock_deps:
        mock_deps.initialize = AsyncMock()
        mock_deps.cleanup = AsyncMock()
        from src.main import app
        with TestClient(app) as c:
            yield c


@pytest.mark.unit
def test_health_returns_ok(client):
    """Health endpoint returns 200 when MongoDB is reachable."""
    with patch("src.routers.health.AgentDependencies") as mock_deps_cls:
        instance = mock_deps_cls.return_value
        instance.initialize = AsyncMock()
        instance.cleanup = AsyncMock()

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["mongodb"] == "connected"


@pytest.mark.unit
def test_health_returns_503_on_mongo_failure(client):
    """Health endpoint returns 503 when MongoDB is unreachable."""
    from pymongo.errors import ConnectionFailure

    with patch("src.routers.health.AgentDependencies") as mock_deps_cls:
        instance = mock_deps_cls.return_value
        instance.initialize = AsyncMock(side_effect=ConnectionFailure("Connection refused"))
        instance.cleanup = AsyncMock()

        response = client.get("/health")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "error"
