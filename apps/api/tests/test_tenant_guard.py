"""Tests for TenantGuardMiddleware."""

import logging

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from src.core.middleware import TenantGuardMiddleware


def _create_app(*, debug: bool = False) -> FastAPI:
    """Create a minimal FastAPI app with the tenant guard middleware."""
    app = FastAPI(debug=debug)
    app.add_middleware(TenantGuardMiddleware)

    @app.get("/api/v1/protected")
    async def protected(request: Request):
        # Simulate a handler that FORGETS to set tenant context
        return {"ok": True}

    @app.get("/api/v1/safe")
    async def safe(request: Request):
        request.state.tenant_id = "tenant-abc"
        return {"ok": True}

    @app.get("/api/v1/auth/login")
    async def login():
        return {"ok": True}

    @app.get("/health")
    async def health():
        return {"ok": True}

    return app


@pytest.mark.unit
def test_guard_warns_on_missing_tenant_context(caplog):
    """Middleware logs warning when protected route lacks tenant context."""
    app = _create_app(debug=False)
    client = TestClient(app)

    with caplog.at_level(logging.WARNING):
        response = client.get("/api/v1/protected")

    assert response.status_code == 200  # Never blocks in prod
    assert any("tenant_id not set" in r.message for r in caplog.records)


@pytest.mark.unit
def test_guard_silent_when_tenant_set(caplog):
    """Middleware stays silent when tenant context is set."""
    app = _create_app(debug=False)
    client = TestClient(app)

    with caplog.at_level(logging.WARNING):
        response = client.get("/api/v1/safe")

    assert response.status_code == 200
    assert not any("tenant_id not set" in r.message for r in caplog.records)


@pytest.mark.unit
def test_guard_skips_auth_routes(caplog):
    """Middleware does not check auth routes."""
    app = _create_app(debug=False)
    client = TestClient(app)

    with caplog.at_level(logging.WARNING):
        response = client.get("/api/v1/auth/login")

    assert response.status_code == 200
    assert not any("tenant_id not set" in r.message for r in caplog.records)


@pytest.mark.unit
def test_guard_skips_health(caplog):
    """Middleware does not check health endpoint."""
    app = _create_app(debug=False)
    client = TestClient(app)

    with caplog.at_level(logging.WARNING):
        response = client.get("/health")

    assert response.status_code == 200
    assert not any("tenant_id not set" in r.message for r in caplog.records)
