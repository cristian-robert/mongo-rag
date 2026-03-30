"""Tests for tenant dependency."""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from tests.conftest import MOCK_TENANT_ID


@pytest.mark.unit
def test_missing_tenant_header_returns_400():
    """Request without X-Tenant-ID header returns 400."""
    from src.core.tenant import get_tenant_id

    app = FastAPI()

    @app.get("/test")
    async def test_endpoint(tenant_id: str = Depends(get_tenant_id)):
        return {"tenant_id": tenant_id}

    client = TestClient(app)
    response = client.get("/test")
    assert response.status_code == 400
    assert "X-Tenant-ID" in response.json()["detail"]


@pytest.mark.unit
def test_valid_tenant_header_returns_tenant_id():
    """Request with valid X-Tenant-ID header extracts tenant_id."""
    from src.core.tenant import get_tenant_id

    app = FastAPI()

    @app.get("/test")
    async def test_endpoint(tenant_id: str = Depends(get_tenant_id)):
        return {"tenant_id": tenant_id}

    client = TestClient(app)
    response = client.get("/test", headers={"X-Tenant-ID": MOCK_TENANT_ID})
    assert response.status_code == 200
    assert response.json()["tenant_id"] == MOCK_TENANT_ID


@pytest.mark.unit
def test_empty_tenant_header_returns_400():
    """Request with empty X-Tenant-ID header returns 400."""
    from src.core.tenant import get_tenant_id

    app = FastAPI()

    @app.get("/test")
    async def test_endpoint(tenant_id: str = Depends(get_tenant_id)):
        return {"tenant_id": tenant_id}

    client = TestClient(app)
    response = client.get("/test", headers={"X-Tenant-ID": ""})
    assert response.status_code == 400
