"""Tests for the GET /api/v1/usage endpoint and quota-enforced flows."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.services.rate_limit import reset_default_limiter
from tests.conftest import MOCK_TENANT_ID, make_auth_header


@pytest.fixture(autouse=True)
def _reset_limiter():
    """Each test starts with a fresh in-memory rate-limiter singleton."""
    reset_default_limiter()
    yield
    reset_default_limiter()


@pytest.fixture
def app_client():
    from src.main import app

    deps = MagicMock()
    deps.initialize = AsyncMock()
    deps.cleanup = AsyncMock()
    deps.db = MagicMock()
    deps.settings = MagicMock()

    deps.documents_collection = MagicMock()
    deps.documents_collection.count_documents = AsyncMock(return_value=2)
    deps.chunks_collection = MagicMock()
    deps.chunks_collection.count_documents = AsyncMock(return_value=42)

    deps.subscriptions_collection = MagicMock()
    deps.subscriptions_collection.find_one = AsyncMock(
        return_value={"plan": "free", "status": "active"}
    )

    usage_doc = {
        "tenant_id": MOCK_TENANT_ID,
        "period_key": "2026-04",
        "period_start": datetime(2026, 4, 1, tzinfo=timezone.utc),
        "period_end": datetime(2026, 5, 1, tzinfo=timezone.utc),
        "queries_count": 17,
        "documents_count": 2,
        "chunks_count": 42,
        "embedding_tokens_count": 1234,
    }
    deps.usage_collection = MagicMock()
    deps.usage_collection.find_one_and_update = AsyncMock(return_value=usage_doc)
    deps.usage_collection.update_one = AsyncMock()

    with TestClient(app) as c:
        app.state.deps = deps
        yield c, deps


@pytest.mark.unit
def test_usage_endpoint_returns_period_metrics(app_client):
    client, _ = app_client
    response = client.get("/api/v1/usage", headers=make_auth_header())

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == MOCK_TENANT_ID
    assert body["plan"] == "free"
    assert body["period_key"] == "2026-04"
    assert body["queries"]["used"] == 17
    assert body["queries"]["limit"] == 100
    assert body["documents"]["used"] == 2
    assert body["chunks"]["used"] == 42
    assert body["rate_limit_per_minute"] == 60


@pytest.mark.unit
def test_usage_endpoint_rejects_api_key(app_client):
    """API keys must NOT be able to read usage (dashboard JWT only)."""
    client, _ = app_client
    response = client.get(
        "/api/v1/usage",
        headers={"Authorization": "Bearer mrag_fake_key_value"},
    )
    # JWT-only dependency returns 403 for API keys
    assert response.status_code == 403


@pytest.mark.unit
def test_usage_endpoint_warning_at_80_percent(app_client):
    """Warning flag flips once the tenant crosses 80% of any limit."""
    client, deps = app_client

    deps.usage_collection.find_one_and_update = AsyncMock(
        return_value={
            "tenant_id": MOCK_TENANT_ID,
            "period_key": "2026-04",
            "period_start": datetime(2026, 4, 1, tzinfo=timezone.utc),
            "period_end": datetime(2026, 5, 1, tzinfo=timezone.utc),
            "queries_count": 85,  # 85/100 = 85%
            "documents_count": 2,
            "chunks_count": 42,
            "embedding_tokens_count": 0,
        }
    )

    response = client.get("/api/v1/usage", headers=make_auth_header())
    assert response.status_code == 200
    body = response.json()
    assert body["queries"]["warning"] is True
    assert body["queries"]["blocked"] is False


# -- Chat quota enforcement --


@pytest.mark.unit
def test_chat_returns_429_when_quota_exhausted(app_client):
    """Chat returns 429 with Retry-After when monthly query quota is hit."""
    client, deps = app_client

    # Quota check increments, returns 101 — will trigger rollback + 429.
    deps.usage_collection.find_one_and_update = AsyncMock(
        return_value={
            "tenant_id": MOCK_TENANT_ID,
            "period_key": "2026-04",
            "period_start": datetime(2026, 4, 1, tzinfo=timezone.utc),
            "period_end": datetime(2099, 5, 1, tzinfo=timezone.utc),
            "queries_count": 101,
        }
    )

    with patch("src.routers.chat.ChatService") as mock_chat_cls:
        mock_chat = MagicMock()
        mock_chat.handle_message = AsyncMock(return_value={})
        mock_chat_cls.return_value = mock_chat

        response = client.post(
            "/api/v1/chat",
            json={"message": "Hi"},
            headers=make_auth_header(),
        )

    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert int(response.headers["Retry-After"]) > 0
    # Quota check must have rolled back the over-the-limit increment
    deps.usage_collection.update_one.assert_awaited()


@pytest.mark.unit
def test_chat_returns_429_when_per_minute_rate_limit_hit(app_client):
    """61st request in a minute (free plan limit) returns 429 from rate limiter."""
    client, deps = app_client

    # Force find_one_and_update to keep returning a low queries_count
    # so the per-minute rate limiter — not the monthly quota — is what
    # produces 429.
    deps.usage_collection.find_one_and_update = AsyncMock(
        return_value={
            "tenant_id": MOCK_TENANT_ID,
            "period_key": "2026-04",
            "period_start": datetime(2026, 4, 1, tzinfo=timezone.utc),
            "period_end": datetime(2099, 5, 1, tzinfo=timezone.utc),
            "queries_count": 1,
        }
    )

    with patch("src.routers.chat.ChatService") as mock_chat_cls:
        mock_chat = MagicMock()
        mock_chat.handle_message = AsyncMock(
            return_value={"answer": "ok", "sources": [], "conversation_id": "c"}
        )
        mock_chat_cls.return_value = mock_chat

        # Free plan: 60 req/min — burst 61 to hit the limit.
        last_status = 200
        for i in range(61):
            r = client.post(
                "/api/v1/chat",
                json={"message": f"hi {i}"},
                headers=make_auth_header(),
            )
            last_status = r.status_code
            if last_status == 429:
                break

        assert last_status == 429


# -- Ingestion quota enforcement --


@pytest.mark.unit
def test_ingest_returns_429_when_document_quota_hit(app_client, tmp_path):
    """Document upload is rejected with 429 once the tenant hits documents_max."""
    client, deps = app_client

    # Free plan caps at 10 documents — fixture already returned 2; bump to 10.
    deps.documents_collection.count_documents = AsyncMock(return_value=10)

    fake_pdf = tmp_path / "doc.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4\n")

    with fake_pdf.open("rb") as fh:
        response = client.post(
            "/api/v1/documents/ingest",
            files={"file": ("doc.pdf", fh, "application/pdf")},
            headers=make_auth_header(),
        )

    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert "10" in response.json()["detail"]
