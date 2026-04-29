"""Unit tests for Supabase JWT verification + tenant routing."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt

from src.core.settings import Settings
from src.core.supabase_auth import reset_jwks_cache, verify_supabase_jwt
from tests.conftest import JWT_SECRET, MOCK_TENANT_ID

PROJECT_REF = "vmuybfmxermgwhmhevou"
SUPABASE_URL = f"https://{PROJECT_REF}.supabase.co"
ISSUER = f"{SUPABASE_URL}/auth/v1"
AUDIENCE = "authenticated"


def _make_settings(**overrides) -> Settings:
    """Build a Settings object with Supabase + required defaults."""
    base = dict(
        mongodb_uri="mongodb://localhost:27017/mongorag-test",
        llm_api_key="test",
        embedding_api_key="test",
        nextauth_secret=JWT_SECRET,
        supabase_url=SUPABASE_URL,
        supabase_project_ref=PROJECT_REF,
        supabase_jwt_audience=AUDIENCE,
    )
    base.update(overrides)
    return Settings(**base)


def _supabase_hs256_token(secret: str, **claims) -> str:
    payload = {
        "sub": "supabase-user-1",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "exp": int(time.time()) + 600,
        "email": "user@example.com",
    }
    payload.update(claims)
    return jose_jwt.encode(payload, secret, algorithm="HS256")


# ---------------------------------------------------------------------------
# Direct verifier tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_valid_hs256_supabase_token_extracts_claims():
    settings = _make_settings(supabase_jwt_secret="supabase-shared-secret-32-chars-aa")
    token = _supabase_hs256_token(
        "supabase-shared-secret-32-chars-aa",
        app_metadata={"tenant_id": MOCK_TENANT_ID},
    )

    claims = await verify_supabase_jwt(token, settings)

    assert claims.sub == "supabase-user-1"
    assert claims.email == "user@example.com"
    assert claims.tenant_id == MOCK_TENANT_ID


@pytest.mark.unit
async def test_invalid_signature_rejected():
    settings = _make_settings(supabase_jwt_secret="supabase-shared-secret-32-chars-aa")
    token = _supabase_hs256_token("a-different-secret-that-doesnt-match!!")

    with pytest.raises(ValueError, match="Invalid or expired token"):
        await verify_supabase_jwt(token, settings)


@pytest.mark.unit
async def test_expired_token_rejected():
    settings = _make_settings(supabase_jwt_secret="supabase-shared-secret-32-chars-aa")
    token = _supabase_hs256_token(
        "supabase-shared-secret-32-chars-aa",
        exp=int(time.time()) - 60,
    )

    with pytest.raises(ValueError, match="Invalid or expired token"):
        await verify_supabase_jwt(token, settings)


@pytest.mark.unit
async def test_wrong_audience_rejected():
    settings = _make_settings(supabase_jwt_secret="supabase-shared-secret-32-chars-aa")
    token = _supabase_hs256_token(
        "supabase-shared-secret-32-chars-aa",
        aud="some-other-audience",
    )

    with pytest.raises(ValueError, match="Invalid or expired token"):
        await verify_supabase_jwt(token, settings)


@pytest.mark.unit
async def test_wrong_issuer_rejected():
    settings = _make_settings(supabase_jwt_secret="supabase-shared-secret-32-chars-aa")
    token = _supabase_hs256_token(
        "supabase-shared-secret-32-chars-aa",
        iss="https://attacker.example.com/auth/v1",
    )

    with pytest.raises(ValueError, match="Invalid or expired token"):
        await verify_supabase_jwt(token, settings)


@pytest.mark.unit
async def test_alg_none_rejected():
    """alg=none must never validate, even if the token has Supabase claims."""
    settings = _make_settings(supabase_jwt_secret="supabase-shared-secret-32-chars-aa")
    # python-jose refuses to encode with `none` unless explicitly enabled, so we
    # craft the token manually.
    import base64
    import json

    def _b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    header = _b64(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    payload = _b64(
        json.dumps(
            {
                "sub": "attacker",
                "iss": ISSUER,
                "aud": AUDIENCE,
                "exp": int(time.time()) + 600,
            }
        ).encode()
    )
    token = f"{header}.{payload}."

    with pytest.raises(ValueError):
        await verify_supabase_jwt(token, settings)


@pytest.mark.unit
async def test_hs256_token_without_configured_secret_rejected():
    """If only JWKS is configured, an HS256 token must not be accepted via the
    asymmetric path (algorithm-confusion guard)."""
    settings = _make_settings()  # no supabase_jwt_secret
    token = _supabase_hs256_token("anything-goes")

    with pytest.raises(ValueError, match="Symmetric algorithm not enabled"):
        await verify_supabase_jwt(token, settings)


@pytest.mark.unit
async def test_tenant_id_falls_back_to_user_metadata():
    settings = _make_settings(supabase_jwt_secret="supabase-shared-secret-32-chars-aa")
    token = _supabase_hs256_token(
        "supabase-shared-secret-32-chars-aa",
        user_metadata={"tenant_id": "from-user-metadata"},
    )

    claims = await verify_supabase_jwt(token, settings)
    assert claims.tenant_id == "from-user-metadata"


@pytest.mark.unit
async def test_app_metadata_wins_over_user_metadata():
    """app_metadata is server-controlled and must be preferred."""
    settings = _make_settings(supabase_jwt_secret="supabase-shared-secret-32-chars-aa")
    token = _supabase_hs256_token(
        "supabase-shared-secret-32-chars-aa",
        app_metadata={"tenant_id": "from-app-metadata"},
        user_metadata={"tenant_id": "user-supplied"},
    )

    claims = await verify_supabase_jwt(token, settings)
    assert claims.tenant_id == "from-app-metadata"


# ---------------------------------------------------------------------------
# JWKS path
# ---------------------------------------------------------------------------


def _rsa_jwk(private_key, kid: str) -> tuple[str, dict]:
    """Return (private_pem, public_jwk) for an RS256 signing key."""
    from cryptography.hazmat.primitives import serialization
    from jose.utils import long_to_base64

    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    pub = private_key.public_key().public_numbers()
    jwk = {
        "kty": "RSA",
        "kid": kid,
        "alg": "RS256",
        "use": "sig",
        "n": long_to_base64(pub.n).decode(),
        "e": long_to_base64(pub.e).decode(),
    }
    return pem, jwk


@pytest.mark.unit
async def test_rs256_token_verified_via_jwks(monkeypatch):
    reset_jwks_cache()
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem, jwk = _rsa_jwk(private, kid="test-kid-1")

    settings = _make_settings()
    token = jose_jwt.encode(
        {
            "sub": "supabase-user-2",
            "iss": ISSUER,
            "aud": AUDIENCE,
            "exp": int(time.time()) + 600,
            "email": "rs@example.com",
            "app_metadata": {"tenant_id": "tenant-rs"},
        },
        pem,
        algorithm="RS256",
        headers={"kid": "test-kid-1"},
    )

    # Stub httpx.AsyncClient.get to return our JWKS.
    captured: list[str] = []

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"keys": [jwk]}

    class _Client:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url):
            captured.append(url)
            return _Resp()

    monkeypatch.setattr("src.core.supabase_auth.httpx.AsyncClient", _Client)

    claims = await verify_supabase_jwt(token, settings)
    assert claims.sub == "supabase-user-2"
    assert claims.tenant_id == "tenant-rs"
    assert captured == [settings.supabase_jwks_url]


@pytest.mark.unit
async def test_jwks_cache_reused_within_ttl(monkeypatch):
    reset_jwks_cache()
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem, jwk = _rsa_jwk(private, kid="cache-kid")

    settings = _make_settings()
    fetch_count = 0

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"keys": [jwk]}

    class _Client:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url):
            nonlocal fetch_count
            fetch_count += 1
            return _Resp()

    monkeypatch.setattr("src.core.supabase_auth.httpx.AsyncClient", _Client)

    def _make_token():
        return jose_jwt.encode(
            {
                "sub": "u",
                "iss": ISSUER,
                "aud": AUDIENCE,
                "exp": int(time.time()) + 600,
                "app_metadata": {"tenant_id": "t"},
            },
            pem,
            algorithm="RS256",
            headers={"kid": "cache-kid"},
        )

    await verify_supabase_jwt(_make_token(), settings)
    await verify_supabase_jwt(_make_token(), settings)
    await verify_supabase_jwt(_make_token(), settings)
    assert fetch_count == 1


# ---------------------------------------------------------------------------
# Integration with get_tenant_id (router-level)
# ---------------------------------------------------------------------------


def _tenant_app(supabase_secret: str | None):
    from src.core import tenant as tenant_mod
    from src.core.tenant import get_tenant_id

    app = FastAPI()

    @app.get("/test")
    async def _h(tenant_id: str = Depends(get_tenant_id)):
        return {"tenant_id": tenant_id}

    settings = _make_settings(
        supabase_jwt_secret=supabase_secret,
        supabase_url=SUPABASE_URL,
    )
    deps = MagicMock()
    deps.settings = settings
    deps.api_keys_collection = MagicMock()
    deps.api_keys_collection.find_one = AsyncMock(return_value=None)
    deps.users_collection = MagicMock()
    deps.users_collection.find_one = AsyncMock(return_value=None)
    app.state.deps = deps

    # Force tenant module to re-read settings on each call
    tenant_mod.load_settings = lambda: settings  # type: ignore[assignment]
    return app, deps


@pytest.mark.unit
def test_supabase_token_routes_via_supabase_path():
    app, deps = _tenant_app(supabase_secret="supabase-shared-secret-32-chars-aa")
    client = TestClient(app)

    token = _supabase_hs256_token(
        "supabase-shared-secret-32-chars-aa",
        app_metadata={"tenant_id": "tenant-from-supabase"},
    )
    resp = client.get("/test", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == "tenant-from-supabase"


@pytest.mark.unit
def test_legacy_nextauth_token_still_works():
    """Backwards compatibility: NextAuth-issued tokens (no Supabase iss) still verify."""
    app, deps = _tenant_app(supabase_secret=None)
    client = TestClient(app)

    token = jose_jwt.encode(
        {"sub": "user-1", "tenant_id": MOCK_TENANT_ID, "role": "owner"},
        JWT_SECRET,
        algorithm="HS256",
    )
    resp = client.get("/test", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == MOCK_TENANT_ID


@pytest.mark.unit
def test_supabase_token_no_tenant_id_falls_back_to_db():
    app, deps = _tenant_app(supabase_secret="supabase-shared-secret-32-chars-aa")
    deps.users_collection.find_one = AsyncMock(
        return_value={
            "_id": "u1",
            "supabase_user_id": "supabase-user-1",
            "tenant_id": "tenant-from-db",
        }
    )
    client = TestClient(app)

    token = _supabase_hs256_token("supabase-shared-secret-32-chars-aa")
    resp = client.get("/test", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == "tenant-from-db"


@pytest.mark.unit
def test_supabase_user_without_tenant_fails_closed():
    app, deps = _tenant_app(supabase_secret="supabase-shared-secret-32-chars-aa")
    deps.users_collection.find_one = AsyncMock(return_value=None)
    client = TestClient(app)

    token = _supabase_hs256_token("supabase-shared-secret-32-chars-aa")
    resp = client.get("/test", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


@pytest.mark.unit
def test_supabase_token_bad_signature_does_not_fall_through_to_nextauth():
    """A token whose `iss` is the Supabase issuer must NOT be re-verified
    against the NextAuth secret on signature failure."""
    app, deps = _tenant_app(supabase_secret="supabase-shared-secret-32-chars-aa")
    client = TestClient(app)

    # Sign with the NextAuth secret but claim Supabase issuer → should be
    # routed to Supabase path, fail signature, return 401 (NOT silently fall
    # back to HS256/NEXTAUTH_SECRET).
    token = jose_jwt.encode(
        {
            "sub": "attacker",
            "iss": ISSUER,
            "aud": AUDIENCE,
            "exp": int(time.time()) + 600,
            "tenant_id": "attacker-tenant",
        },
        JWT_SECRET,
        algorithm="HS256",
    )
    resp = client.get("/test", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
