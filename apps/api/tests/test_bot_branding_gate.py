"""Tests for the route-layer branding_text plan gate (#87)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from tests.conftest import make_auth_header


@pytest.fixture
def bot_client(mock_deps):
    from src.main import app

    with TestClient(app) as c:
        app.state.deps = mock_deps
        yield c


def _api_bot(bot_id: str, tenant_id: str = "test-tenant-001", **overrides) -> dict:
    now = datetime(2026, 4, 4, tzinfo=timezone.utc)
    base = {
        "id": bot_id,
        "tenant_id": tenant_id,
        "name": "Support Bot",
        "slug": "support-bot",
        "description": None,
        "system_prompt": "You are helpful",
        "welcome_message": "Hi!",
        "tone": "professional",
        "is_public": False,
        "model_config": {"temperature": 0.2, "max_tokens": 1024},
        "widget_config": {
            "primary_color": "#0f172a",
            "position": "bottom-right",
            "avatar_url": None,
        },
        "document_filter": {"mode": "all", "document_ids": []},
        "created_at": now,
        "updated_at": now,
    }
    base.update(overrides)
    return base


def _set_plan(mock_deps, plan: str, status: str = "active") -> None:
    mock_deps.subscriptions_collection.find_one = AsyncMock(
        return_value={"plan": plan, "status": status}
    )


@pytest.mark.unit
def test_create_bot_branding_text_blocked_for_free_plan(bot_client, mock_deps):
    _set_plan(mock_deps, "free")
    with patch("src.routers.bots.BotService") as mock_cls:
        instance = mock_cls.return_value
        instance.count_for_tenant = AsyncMock(return_value=0)
        instance.create = AsyncMock(return_value=_api_bot(str(ObjectId())))

        response = bot_client.post(
            "/api/v1/bots",
            json={
                "name": "Bot",
                "slug": "bot-x",
                "system_prompt": "you are helpful",
                "widget_config": {"branding_text": "Acme Inc"},
            },
            headers=make_auth_header(),
        )

    assert response.status_code == 403
    assert "paid plan" in response.json()["detail"].lower()
    instance.create.assert_not_called()


@pytest.mark.unit
def test_create_bot_branding_text_allowed_for_pro_plan(bot_client, mock_deps):
    _set_plan(mock_deps, "pro")
    bot_id = str(ObjectId())
    with patch("src.routers.bots.BotService") as mock_cls:
        instance = mock_cls.return_value
        instance.count_for_tenant = AsyncMock(return_value=0)
        instance.create = AsyncMock(return_value=_api_bot(bot_id))

        response = bot_client.post(
            "/api/v1/bots",
            json={
                "name": "Bot",
                "slug": "bot-x",
                "system_prompt": "you are helpful",
                "widget_config": {"branding_text": "Acme Inc"},
            },
            headers=make_auth_header(),
        )

    assert response.status_code == 201
    instance.create.assert_awaited_once()


@pytest.mark.unit
def test_update_bot_branding_text_blocked_for_free_plan(bot_client, mock_deps):
    _set_plan(mock_deps, "free")
    bot_id = str(ObjectId())
    with patch("src.routers.bots.BotService") as mock_cls:
        instance = mock_cls.return_value
        instance.update = AsyncMock(return_value=_api_bot(bot_id))

        response = bot_client.put(
            f"/api/v1/bots/{bot_id}",
            json={"widget_config": {"branding_text": "Acme Inc"}},
            headers=make_auth_header(),
        )

    assert response.status_code == 403
    instance.update.assert_not_called()


@pytest.mark.unit
def test_update_bot_branding_text_allowed_for_starter_plan(bot_client, mock_deps):
    _set_plan(mock_deps, "starter")
    bot_id = str(ObjectId())
    with patch("src.routers.bots.BotService") as mock_cls:
        instance = mock_cls.return_value
        instance.update = AsyncMock(return_value=_api_bot(bot_id))

        response = bot_client.put(
            f"/api/v1/bots/{bot_id}",
            json={"widget_config": {"branding_text": "Acme"}},
            headers=make_auth_header(),
        )

    assert response.status_code == 200


@pytest.mark.unit
def test_update_without_branding_skips_plan_gate(bot_client, mock_deps):
    """If branding_text isn't in the payload, the gate must not be invoked.

    Avoid an unrelated plan read on every update — common-path performance.
    """
    _set_plan(mock_deps, "free")
    bot_id = str(ObjectId())
    with patch("src.routers.bots.BotService") as mock_cls:
        instance = mock_cls.return_value
        instance.update = AsyncMock(return_value=_api_bot(bot_id))

        response = bot_client.put(
            f"/api/v1/bots/{bot_id}",
            json={"name": "Renamed"},
            headers=make_auth_header(),
        )

    assert response.status_code == 200
    # If the gate were invoked, find_one would have been awaited.
    mock_deps.subscriptions_collection.find_one.assert_not_called()


@pytest.mark.unit
def test_inactive_subscription_treated_as_free(bot_client, mock_deps):
    """A 'past_due' subscription with plan=pro should be treated as free."""
    _set_plan(mock_deps, "pro", status="past_due")
    with patch("src.routers.bots.BotService") as mock_cls:
        instance = mock_cls.return_value
        instance.count_for_tenant = AsyncMock(return_value=0)

        response = bot_client.post(
            "/api/v1/bots",
            json={
                "name": "Bot",
                "slug": "bot-x",
                "system_prompt": "you are helpful",
                "widget_config": {"branding_text": "Acme"},
            },
            headers=make_auth_header(),
        )

    assert response.status_code == 403
