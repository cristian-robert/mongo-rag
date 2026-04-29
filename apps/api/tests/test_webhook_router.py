"""Tests for the webhooks router (CRUD + tenant isolation)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from tests.conftest import make_auth_header, make_auth_header_b


@pytest.fixture
def webhook_client(mock_deps):
    from src.main import app

    with TestClient(app) as c:
        app.state.deps = mock_deps
        yield c


def _api_webhook(webhook_id: str) -> dict:
    now = datetime(2026, 4, 1, tzinfo=timezone.utc)
    return {
        "id": webhook_id,
        "url": "https://example.com/hook",
        "events": ["document.ingested"],
        "description": None,
        "active": True,
        "secret_prefix": "abc123",
        "created_at": now,
        "updated_at": now,
    }


@pytest.mark.unit
def test_create_webhook_returns_secret_once(webhook_client):
    webhook_id = str(ObjectId())
    with patch("src.routers.webhooks.WebhookService") as mock_cls:
        instance = mock_cls.return_value
        instance.create = AsyncMock(
            return_value=(_api_webhook(webhook_id), "whsec_thisisthesecret")
        )

        response = webhook_client.post(
            "/api/v1/webhooks",
            json={
                "url": "https://example.com/hook",
                "events": ["document.ingested"],
            },
            headers=make_auth_header(),
        )

    assert response.status_code == 201
    body = response.json()
    assert body["secret"] == "whsec_thisisthesecret"
    assert body["id"] == webhook_id


@pytest.mark.unit
def test_create_webhook_requires_jwt_rejects_api_key(webhook_client):
    response = webhook_client.post(
        "/api/v1/webhooks",
        json={"url": "https://example.com/h", "events": ["chat.completed"]},
        headers={"Authorization": "Bearer mrag_someapikey1234567890123456"},
    )
    assert response.status_code == 403


@pytest.mark.unit
def test_create_webhook_unauthenticated(webhook_client):
    response = webhook_client.post(
        "/api/v1/webhooks",
        json={"url": "https://example.com/h", "events": ["chat.completed"]},
    )
    assert response.status_code == 401


@pytest.mark.unit
def test_create_webhook_rejects_unknown_event(webhook_client):
    response = webhook_client.post(
        "/api/v1/webhooks",
        json={"url": "https://example.com/h", "events": ["not.a.real.event"]},
        headers=make_auth_header(),
    )
    assert response.status_code == 422


@pytest.mark.unit
def test_create_webhook_rejects_duplicate_events(webhook_client):
    response = webhook_client.post(
        "/api/v1/webhooks",
        json={
            "url": "https://example.com/h",
            "events": ["chat.completed", "chat.completed"],
        },
        headers=make_auth_header(),
    )
    assert response.status_code == 422


@pytest.mark.unit
def test_list_webhooks_filters_by_tenant(webhook_client):
    """Service receives the tenant_id from the JWT and never any other source."""
    captured = {}

    async def fake_list(tenant_id: str):
        captured["tenant_id"] = tenant_id
        return []

    with patch("src.routers.webhooks.WebhookService") as mock_cls:
        instance = mock_cls.return_value
        instance.list_for_tenant = AsyncMock(side_effect=fake_list)

        response = webhook_client.get("/api/v1/webhooks", headers=make_auth_header_b())

    assert response.status_code == 200
    assert captured["tenant_id"] == "test-tenant-002"


@pytest.mark.unit
def test_get_webhook_404_when_other_tenant(webhook_client):
    """Service receives only this tenant's id; cross-tenant get returns 404."""
    other_id = str(ObjectId())
    with patch("src.routers.webhooks.WebhookService") as mock_cls:
        instance = mock_cls.return_value
        instance.get_response = AsyncMock(return_value=None)

        response = webhook_client.get(f"/api/v1/webhooks/{other_id}", headers=make_auth_header())
    assert response.status_code == 404


@pytest.mark.unit
def test_delete_webhook_404_when_not_found(webhook_client):
    other_id = str(ObjectId())
    with patch("src.routers.webhooks.WebhookService") as mock_cls:
        instance = mock_cls.return_value
        instance.delete = AsyncMock(return_value=False)

        response = webhook_client.delete(f"/api/v1/webhooks/{other_id}", headers=make_auth_header())
    assert response.status_code == 404


@pytest.mark.unit
def test_test_fire_rejects_unsubscribed_event(webhook_client):
    webhook_id = str(ObjectId())
    with patch("src.routers.webhooks.WebhookService") as mock_cls:
        instance = mock_cls.return_value
        instance.get = AsyncMock(
            return_value={
                "_id": ObjectId(webhook_id),
                "tenant_id": "test-tenant-001",
                "url": "https://example.com/h",
                "events": ["document.ingested"],
                "secret": "whsec_x",
            }
        )

        response = webhook_client.post(
            f"/api/v1/webhooks/{webhook_id}/test",
            json={"event": "chat.completed"},
            headers=make_auth_header(),
        )
    assert response.status_code == 409


@pytest.mark.unit
def test_event_types_endpoint_returns_full_taxonomy(webhook_client):
    response = webhook_client.get("/api/v1/webhooks/events", headers=make_auth_header())
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {
        "document.ingested",
        "document.deleted",
        "chat.completed",
        "subscription.updated",
    }
