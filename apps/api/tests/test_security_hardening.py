"""Security hardening tests: CORS, security headers, body-size, input strictness.

These tests use a tiny FastAPI app that mounts the same middleware as the
production app so we can exercise it without standing up MongoDB.
"""

import os
from typing import Iterator

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from src.core.middleware import (
    BodySizeLimitMiddleware,
    SecurityHeadersMiddleware,
)


def _make_app(
    *,
    origins: list[str],
    is_production: bool = False,
    body_limit: int = 1024,
) -> FastAPI:
    app = FastAPI()

    app.add_middleware(BodySizeLimitMiddleware, max_bytes=body_limit)
    app.add_middleware(SecurityHeadersMiddleware, is_production=is_production)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,
    )

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"ok": "yes"}

    @app.post("/echo")
    async def echo(payload: dict) -> dict:
        return payload

    return app


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = _make_app(origins=["http://localhost:3100"])
    with TestClient(app) as c:
        yield c


@pytest.mark.unit
def test_security_headers_present_on_get(client: TestClient) -> None:
    """Baseline security headers attach to every response."""
    r = client.get("/ping")

    assert r.status_code == 200
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Permissions-Policy" in r.headers
    assert r.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert r.headers["Cache-Control"] == "no-store"


@pytest.mark.unit
def test_hsts_only_in_production() -> None:
    """HSTS must not be set in development (would lock localhost into HTTPS)."""
    dev = TestClient(_make_app(origins=["http://localhost:3100"], is_production=False))
    prod = TestClient(_make_app(origins=["https://app.example.com"], is_production=True))

    assert "Strict-Transport-Security" not in dev.get("/ping").headers
    assert "max-age=" in prod.get("/ping").headers["Strict-Transport-Security"]


@pytest.mark.unit
def test_cors_allows_listed_origin() -> None:
    """A request from an allow-listed origin gets the matching CORS header back."""
    app = _make_app(origins=["http://localhost:3100"])
    client = TestClient(app)

    r = client.options(
        "/echo",
        headers={
            "Origin": "http://localhost:3100",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert r.status_code in (200, 204)
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3100"
    assert r.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.unit
def test_cors_blocks_unlisted_origin() -> None:
    """An origin not on the allow-list does not receive the CORS allow header."""
    app = _make_app(origins=["http://localhost:3100"])
    client = TestClient(app)

    r = client.options(
        "/echo",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )

    # CORS middleware does not echo unknown origins back.
    assert r.headers.get("access-control-allow-origin") != "https://evil.example.com"


@pytest.mark.unit
def test_cors_does_not_reflect_arbitrary_origins() -> None:
    """Confirm origin reflection is impossible — defense against CORS bypass."""
    app = _make_app(origins=["http://localhost:3100"])
    client = TestClient(app)

    r = client.get("/ping", headers={"Origin": "null"})

    assert r.headers.get("access-control-allow-origin") not in {"null", "*"}


@pytest.mark.unit
def test_body_size_limit_rejects_large_content_length() -> None:
    """Requests exceeding the configured body limit return 413."""
    app = _make_app(origins=["http://localhost:3100"], body_limit=128)
    client = TestClient(app)

    big = "x" * 1024
    r = client.post(
        "/echo",
        content=f'{{"v":"{big}"}}',
        headers={
            "Content-Type": "application/json",
        },
    )

    assert r.status_code == 413


@pytest.mark.unit
def test_body_size_limit_allows_small_payload() -> None:
    """Requests inside the limit pass through normally."""
    app = _make_app(origins=["http://localhost:3100"], body_limit=4096)
    client = TestClient(app)

    r = client.post("/echo", json={"hello": "world"})

    assert r.status_code == 200
    assert r.json() == {"hello": "world"}


@pytest.mark.unit
def test_body_size_limit_invalid_content_length_400() -> None:
    """A non-numeric Content-Length is rejected with 400."""
    app = _make_app(origins=["http://localhost:3100"], body_limit=4096)
    client = TestClient(app)

    r = client.post(
        "/echo",
        content=b'{"a":1}',
        headers={
            "Content-Type": "application/json",
            "Content-Length": "not-a-number",
        },
    )

    assert r.status_code == 400


@pytest.mark.unit
def test_body_size_exempt_upload_path_passes_large_content_length() -> None:
    """Multipart upload paths are exempt — size enforced by the handler."""
    app = FastAPI()
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=10)

    @app.post("/api/v1/documents/ingest")
    async def ingest() -> dict[str, str]:
        return {"ok": "yes"}

    client = TestClient(app)
    r = client.post(
        "/api/v1/documents/ingest",
        content=b"x" * 200,
        headers={"Content-Type": "application/octet-stream"},
    )

    assert r.status_code == 200


# --- Settings & CORS list parsing ---


@pytest.mark.unit
def test_settings_cors_origins_list_parses_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    """cors_origins_list parses a comma-separated env value into a clean list."""
    from src.core.settings import Settings

    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("LLM_API_KEY", "x")
    monkeypatch.setenv("EMBEDDING_API_KEY", "x")
    monkeypatch.setenv("NEXTAUTH_SECRET", "y" * 32)
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        "https://app.example.com, https://admin.example.com ,",
    )

    s = Settings()
    assert s.cors_origins_list == [
        "https://app.example.com",
        "https://admin.example.com",
    ]


@pytest.mark.unit
def test_settings_is_production_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """is_production reflects APP_ENV exactly."""
    from src.core.settings import Settings

    for k, v in {
        "MONGODB_URI": "mongodb://localhost:27017",
        "LLM_API_KEY": "x",
        "EMBEDDING_API_KEY": "x",
        "NEXTAUTH_SECRET": "y" * 32,
    }.items():
        monkeypatch.setenv(k, v)

    monkeypatch.setenv("APP_ENV", "production")
    assert Settings().is_production is True
    monkeypatch.setenv("APP_ENV", "development")
    assert Settings().is_production is False


# --- Input validation strictness ---


@pytest.mark.unit
def test_chat_request_rejects_unknown_fields() -> None:
    """ChatRequest must forbid mass-assignment of unexpected fields."""
    from pydantic import ValidationError

    from src.models.api import ChatRequest

    with pytest.raises(ValidationError):
        ChatRequest(
            message="hello",
            conversation_id=None,
            tenant_id="other-tenant",  # type: ignore[call-arg]
        )


@pytest.mark.unit
def test_chat_request_caps_message_length() -> None:
    """ChatRequest enforces a maximum message length."""
    from pydantic import ValidationError

    from src.models.api import ChatRequest

    with pytest.raises(ValidationError):
        ChatRequest(message="a" * 10_001)


@pytest.mark.unit
def test_signup_request_rejects_extra_fields() -> None:
    from pydantic import ValidationError

    from src.models.api import SignupRequest

    with pytest.raises(ValidationError):
        SignupRequest(
            email="foo@example.com",
            password="password123",
            organization_name="Acme",
            role="owner",  # type: ignore[call-arg]
        )


@pytest.mark.unit
def test_create_key_request_rejects_extra_fields() -> None:
    from pydantic import ValidationError

    from src.models.api import CreateKeyRequest

    with pytest.raises(ValidationError):
        CreateKeyRequest(
            name="prod",
            permissions=["chat", "search"],
            tenant_id="other-tenant",  # type: ignore[call-arg]
        )


@pytest.mark.unit
def test_ws_message_rejects_unknown_type() -> None:
    """WSMessage type must be one of the literal values (no injection)."""
    from pydantic import ValidationError

    from src.models.api import WSMessage

    with pytest.raises(ValidationError):
        WSMessage(type="evil")  # type: ignore[arg-type]


@pytest.mark.unit
def test_checkout_request_rejects_extra_fields() -> None:
    from pydantic import ValidationError

    from src.models.billing import CheckoutRequest, ModelTier
    from src.models.tenant import PlanTier

    with pytest.raises(ValidationError):
        CheckoutRequest(
            plan=PlanTier.PRO,
            model_tier=ModelTier.STARTER,
            success_url="https://app.example.com/ok",
            cancel_url="https://app.example.com/cancel",
            tenant_id="other-tenant",  # type: ignore[call-arg]
        )


# --- Billing redirect URL hardening ---


@pytest.mark.unit
def test_validate_redirect_url_rejects_userinfo() -> None:
    """Embedded credentials are rejected to block phishing-style redirects."""
    from fastapi import HTTPException

    from src.routers.billing import _validate_redirect_url

    with pytest.raises(HTTPException) as exc:
        _validate_redirect_url("https://attacker@evil.example.com/", "success_url")
    assert exc.value.status_code == 400


@pytest.mark.unit
def test_validate_redirect_url_rejects_private_ip() -> None:
    """Private/loopback IP-literal hosts are rejected (SSRF hardening)."""
    from fastapi import HTTPException

    from src.routers.billing import _validate_redirect_url

    for url in (
        "https://10.0.0.1/cb",
        "https://192.168.1.5/cb",
        "https://169.254.169.254/latest/meta-data/",
    ):
        with pytest.raises(HTTPException) as exc:
            _validate_redirect_url(url, "success_url")
        assert exc.value.status_code == 400


@pytest.mark.unit
def test_validate_redirect_url_allows_https_public() -> None:
    from src.routers.billing import _validate_redirect_url

    # Should not raise.
    _validate_redirect_url("https://app.example.com/billing/success", "success_url")


# --- Auth IP rate limiter ---


@pytest.mark.unit
async def test_enforce_auth_ip_rate_limit_blocks_after_threshold() -> None:
    """A burst of requests from the same IP eventually returns 429."""
    from fastapi import HTTPException

    from src.core.rate_limit_dep import enforce_auth_ip_rate_limit
    from src.services.rate_limit import reset_default_limiter

    reset_default_limiter()

    class _Client:
        host = "203.0.113.10"

    class _Req:
        headers: dict[str, str] = {"x-forwarded-for": "203.0.113.10"}
        client = _Client()

    # 20 calls allowed, 21st should raise.
    for _ in range(20):
        await enforce_auth_ip_rate_limit(_Req())  # type: ignore[arg-type]

    with pytest.raises(HTTPException) as exc:
        await enforce_auth_ip_rate_limit(_Req())  # type: ignore[arg-type]

    assert exc.value.status_code == 429
    assert "Retry-After" in exc.value.headers


# --- Secret hygiene smoke test ---


@pytest.mark.unit
def test_no_live_stripe_keys_in_non_test_code() -> None:
    """Static check: no sk_live_ keys checked into non-test files under apps/.

    Test files may legitimately contain placeholder ``sk_live_…`` strings
    as redaction fixtures; production code must not.
    """
    import re

    pattern = re.compile(rb"sk_live_[A-Za-z0-9]{20,}")
    here = os.path.dirname(__file__)
    repo_apps = os.path.normpath(os.path.join(here, "..", "..", ".."))

    offenders: list[str] = []
    for root, dirs, files in os.walk(os.path.join(repo_apps, "apps")):
        dirs[:] = [
            d
            for d in dirs
            if d
            not in {
                "node_modules",
                ".next",
                "__pycache__",
                ".pytest_cache",
                ".venv",
                "dist",
                "build",
                "tests",
                "__tests__",
            }
        ]
        for name in files:
            if (
                name.startswith("test_")
                or name.endswith(".test.ts")
                or name.endswith(".test.tsx")
                or name.endswith(".spec.ts")
            ):
                continue
            path = os.path.join(root, name)
            try:
                with open(path, "rb") as f:
                    if pattern.search(f.read()):
                        offenders.append(path)
            except OSError:
                continue

    assert not offenders, f"Live Stripe keys found in: {offenders}"
