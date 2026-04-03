"""Tests for JWT-based tenant extraction."""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from jose import jwt

MOCK_SECRET = "test-secret-for-unit-tests-minimum-32chars"
MOCK_TENANT_ID = "tenant-abc-123"


@pytest.fixture
def jwt_app():
    """Create a test app with JWT-based tenant extraction."""
    from src.core.tenant import get_tenant_id

    app = FastAPI()

    @app.get("/test")
    async def test_endpoint(tenant_id: str = Depends(get_tenant_id)):
        return {"tenant_id": tenant_id}

    return TestClient(app)


def _make_jwt(payload: dict, secret: str = MOCK_SECRET) -> str:
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.mark.unit
def test_jwt_extracts_tenant_id(jwt_app):
    """Valid JWT in Authorization header extracts tenant_id."""
    token = _make_jwt({"sub": "user-123", "tenant_id": MOCK_TENANT_ID, "role": "owner"})
    response = jwt_app.get("/test", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["tenant_id"] == MOCK_TENANT_ID


@pytest.mark.unit
def test_jwt_missing_tenant_id_claim(jwt_app):
    """JWT without tenant_id claim returns 401."""
    token = _make_jwt({"sub": "user-123"})
    response = jwt_app.get("/test", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


@pytest.mark.unit
def test_jwt_invalid_token(jwt_app):
    """Invalid JWT returns 401."""
    response = jwt_app.get("/test", headers={"Authorization": "Bearer invalid.token.here"})
    assert response.status_code == 401


@pytest.mark.unit
def test_jwt_wrong_secret(jwt_app):
    """JWT signed with wrong secret returns 401."""
    token = _make_jwt({"sub": "user-123", "tenant_id": MOCK_TENANT_ID}, secret="wrong-secret!!")
    response = jwt_app.get("/test", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


@pytest.mark.unit
def test_no_auth_header_returns_401(jwt_app):
    """Request without Authorization header returns 401."""
    response = jwt_app.get("/test")
    assert response.status_code == 401


@pytest.mark.unit
def test_x_tenant_id_header_still_rejected(jwt_app):
    """Old X-Tenant-ID header alone no longer works."""
    response = jwt_app.get("/test", headers={"X-Tenant-ID": MOCK_TENANT_ID})
    assert response.status_code == 401
