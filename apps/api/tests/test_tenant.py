"""Tests for tenant dependency (JWT-based)."""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from tests.conftest import JWT_SECRET, MOCK_TENANT_ID


@pytest.fixture
def tenant_app():
    """Create a test app with JWT tenant extraction."""
    from src.core.tenant import get_tenant_id

    app = FastAPI()

    @app.get("/test")
    async def test_endpoint(tenant_id: str = Depends(get_tenant_id)):
        return {"tenant_id": tenant_id}

    return TestClient(app)


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
