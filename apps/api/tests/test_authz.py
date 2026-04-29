"""Tests for the role-based authorization helper (require_role)."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from jose import jwt

JWT_SECRET = "test-secret-for-unit-tests-minimum-32chars"


def _token(role: str, tenant_id: str = "tenant-1", sub: str = "user-1") -> str:
    return jwt.encode(
        {"sub": sub, "tenant_id": tenant_id, "role": role},
        JWT_SECRET,
        algorithm="HS256",
    )


def _hdr(role: str) -> dict:
    return {"Authorization": f"Bearer {_token(role)}"}


@pytest.fixture
def app():
    from src.core.authz import Principal, require_role
    from src.models.user import UserRole

    app = FastAPI()

    @app.get("/owner-only")
    async def owner(p: Principal = Depends(require_role(UserRole.OWNER))):
        return {"ok": True}

    @app.get("/admin-plus")
    async def admin(p: Principal = Depends(require_role(UserRole.ADMIN))):
        return {"ok": True}

    @app.get("/member-plus")
    async def member(p: Principal = Depends(require_role(UserRole.MEMBER))):
        return {"ok": True}

    deps = MagicMock()
    deps.api_keys_collection.find_one = AsyncMock(return_value=None)
    app.state.deps = deps
    return TestClient(app)


@pytest.mark.unit
def test_owner_passes_all_gates(app):
    for path in ("/owner-only", "/admin-plus", "/member-plus"):
        assert app.get(path, headers=_hdr("owner")).status_code == 200


@pytest.mark.unit
def test_admin_blocked_from_owner_only(app):
    assert app.get("/owner-only", headers=_hdr("admin")).status_code == 403
    assert app.get("/admin-plus", headers=_hdr("admin")).status_code == 200


@pytest.mark.unit
def test_member_blocked_from_admin(app):
    assert app.get("/admin-plus", headers=_hdr("member")).status_code == 403
    assert app.get("/member-plus", headers=_hdr("member")).status_code == 200


@pytest.mark.unit
def test_viewer_blocked_from_member(app):
    assert app.get("/member-plus", headers=_hdr("viewer")).status_code == 403


@pytest.mark.unit
def test_unknown_role_rejected(app):
    assert app.get("/member-plus", headers=_hdr("super-admin")).status_code == 401


@pytest.mark.unit
def test_missing_role_claim_rejected(app):
    token = jwt.encode({"sub": "u", "tenant_id": "t"}, JWT_SECRET, algorithm="HS256")
    r = app.get("/member-plus", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


@pytest.mark.unit
def test_api_key_rejected(app):
    r = app.get("/member-plus", headers={"Authorization": "Bearer mrag_abcdef123"})
    assert r.status_code == 403
