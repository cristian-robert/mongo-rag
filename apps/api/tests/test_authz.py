"""Tests for the role-based authorization helper (require_role)."""

from time import time as _time
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


# -- Supabase JWT path (issue #73) --

SUPABASE_ISSUER = "https://supa-test.supabase.co/auth/v1"
SUPABASE_AUDIENCE = "authenticated"
SUPABASE_HS256_SECRET = "supabase-shared-secret-32-chars-aa"


def _supabase_token(
    *,
    sub: str = "supabase-user-1",
    email: str = "u@example.com",
    extra_claims: dict | None = None,
) -> str:
    payload = {
        "sub": sub,
        "email": email,
        "iss": SUPABASE_ISSUER,
        "aud": SUPABASE_AUDIENCE,
        "exp": int(_time()) + 600,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, SUPABASE_HS256_SECRET, algorithm="HS256")


@pytest.fixture
def supabase_app(monkeypatch):
    """An app whose Settings advertise Supabase HS256 as enabled."""
    monkeypatch.setenv("SUPABASE_URL", SUPABASE_ISSUER.replace("/auth/v1", ""))
    monkeypatch.setenv("SUPABASE_PROJECT_REF", "supa-test")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SUPABASE_HS256_SECRET)
    monkeypatch.setenv("SUPABASE_JWT_AUDIENCE", SUPABASE_AUDIENCE)

    from src.core.authz import Principal, require_role
    from src.core.deps import get_deps
    from src.models.user import UserRole

    app = FastAPI()

    @app.get("/admin-plus")
    async def admin(p: Principal = Depends(require_role(UserRole.ADMIN))):
        return {"ok": True, "tenant_id": p.tenant_id, "role": p.role, "user_id": p.user_id}

    deps = MagicMock()
    deps.users_collection.find_one = AsyncMock(
        return_value={
            "_id": "mongo-uid-1",
            "supabase_user_id": "supabase-user-1",
            "tenant_id": "tenant-supa-1",
            "role": "admin",
            "email": "u@example.com",
        }
    )
    app.dependency_overrides[get_deps] = lambda: deps
    return TestClient(app), deps


@pytest.mark.unit
def test_supabase_token_resolves_principal_with_role(supabase_app):
    client, _ = supabase_app
    r = client.get("/admin-plus", headers={"Authorization": f"Bearer {_supabase_token()}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tenant_id"] == "tenant-supa-1"
    assert body["role"] == "admin"
    assert body["user_id"] == "mongo-uid-1"


@pytest.mark.unit
def test_supabase_token_user_not_found_is_401(supabase_app):
    client, deps = supabase_app
    deps.users_collection.find_one = AsyncMock(return_value=None)
    r = client.get("/admin-plus", headers={"Authorization": f"Bearer {_supabase_token()}"})
    assert r.status_code == 401


@pytest.mark.unit
def test_supabase_token_with_role_below_required_is_403(supabase_app):
    client, deps = supabase_app
    deps.users_collection.find_one = AsyncMock(
        return_value={
            "_id": "mongo-uid-1",
            "supabase_user_id": "supabase-user-1",
            "tenant_id": "tenant-supa-1",
            "role": "viewer",
            "email": "u@example.com",
        }
    )
    r = client.get("/admin-plus", headers={"Authorization": f"Bearer {_supabase_token()}"})
    assert r.status_code == 403


@pytest.mark.unit
def test_legacy_nextauth_token_still_works(supabase_app):
    """Belt-and-braces: the NextAuth HS256 fallback must still resolve."""
    client, _ = supabase_app
    r = client.get("/admin-plus", headers=_hdr("admin"))
    assert r.status_code == 200
