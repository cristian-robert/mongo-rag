"""Tests for the bots router."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from src.services.bot import BotSlugTakenError
from tests.conftest import make_auth_header, make_auth_header_b


@pytest.fixture
def bot_client(mock_deps):
    from src.main import app

    with TestClient(app) as c:
        app.state.deps = mock_deps
        yield c


def _api_bot(bot_id: str, tenant_id: str = "test-tenant-001") -> dict:
    now = datetime(2026, 4, 4, tzinfo=timezone.utc)
    return {
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


@pytest.mark.unit
def test_create_bot_returns_201(bot_client):
    bot_id = str(ObjectId())
    with patch("src.routers.bots.BotService") as mock_cls:
        instance = mock_cls.return_value
        instance.count_for_tenant = AsyncMock(return_value=0)
        instance.create = AsyncMock(return_value=_api_bot(bot_id))

        response = bot_client.post(
            "/api/v1/bots",
            json={
                "name": "Support Bot",
                "slug": "support-bot",
                "system_prompt": "You are helpful and friendly.",
                "welcome_message": "Hi!",
            },
            headers=make_auth_header(),
        )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == bot_id
    assert data["slug"] == "support-bot"


@pytest.mark.unit
def test_create_bot_requires_jwt(bot_client):
    response = bot_client.post(
        "/api/v1/bots",
        json={"name": "x", "slug": "x", "system_prompt": "you are helpful"},
        headers={"Authorization": "Bearer mrag_someapikey1234567890123456"},
    )
    assert response.status_code == 403


@pytest.mark.unit
def test_create_bot_unauthenticated(bot_client):
    response = bot_client.post(
        "/api/v1/bots",
        json={"name": "x", "slug": "x", "system_prompt": "you are helpful"},
    )
    assert response.status_code == 401


@pytest.mark.unit
def test_create_bot_rejects_invalid_slug(bot_client):
    response = bot_client.post(
        "/api/v1/bots",
        json={
            "name": "Bot",
            "slug": "Invalid Slug!",
            "system_prompt": "you are helpful",
        },
        headers=make_auth_header(),
    )
    assert response.status_code == 422


@pytest.mark.unit
def test_create_bot_returns_409_on_slug_collision(bot_client):
    with patch("src.routers.bots.BotService") as mock_cls:
        instance = mock_cls.return_value
        instance.count_for_tenant = AsyncMock(return_value=0)
        instance.create = AsyncMock(side_effect=BotSlugTakenError("taken"))

        response = bot_client.post(
            "/api/v1/bots",
            json={
                "name": "Bot",
                "slug": "support-bot",
                "system_prompt": "you are helpful",
            },
            headers=make_auth_header(),
        )
    assert response.status_code == 409


@pytest.mark.unit
def test_create_bot_returns_409_when_at_limit(bot_client):
    with (
        patch("src.routers.bots.BotService") as mock_cls,
        patch("src.routers.bots.MAX_BOTS_PER_TENANT", 2),
    ):
        instance = mock_cls.return_value
        instance.count_for_tenant = AsyncMock(return_value=2)

        response = bot_client.post(
            "/api/v1/bots",
            json={
                "name": "Bot",
                "slug": "support-bot",
                "system_prompt": "you are helpful",
            },
            headers=make_auth_header(),
        )
    assert response.status_code == 409


@pytest.mark.unit
def test_list_bots_returns_for_tenant(bot_client):
    bot_id = str(ObjectId())
    with patch("src.routers.bots.BotService") as mock_cls:
        instance = mock_cls.return_value
        instance.list_for_tenant = AsyncMock(return_value=[_api_bot(bot_id)])

        response = bot_client.get("/api/v1/bots", headers=make_auth_header())

    assert response.status_code == 200
    data = response.json()
    assert len(data["bots"]) == 1
    assert data["bots"][0]["id"] == bot_id
    instance.list_for_tenant.assert_awaited_once_with("test-tenant-001")


@pytest.mark.unit
def test_get_bot_404_for_unknown_id(bot_client):
    with patch("src.routers.bots.BotService") as mock_cls:
        instance = mock_cls.return_value
        instance.get = AsyncMock(return_value=None)

        response = bot_client.get(f"/api/v1/bots/{ObjectId()}", headers=make_auth_header())
    assert response.status_code == 404


@pytest.mark.unit
def test_get_bot_404_for_cross_tenant(bot_client):
    """Tenant B requesting Tenant A's bot must get a 404, not 403 — never leak existence."""
    with patch("src.routers.bots.BotService") as mock_cls:
        instance = mock_cls.return_value
        # Service returns None because the (id, tenant) tuple doesn't match.
        instance.get = AsyncMock(return_value=None)

        response = bot_client.get(f"/api/v1/bots/{ObjectId()}", headers=make_auth_header_b())

    assert response.status_code == 404
    instance.get.assert_awaited_once()
    # Ensure the tenant from JWT B was passed, not from query/body.
    args, kwargs = instance.get.call_args
    assert kwargs.get("tenant_id") == "test-tenant-002"


@pytest.mark.unit
def test_update_bot_404_for_cross_tenant(bot_client):
    with patch("src.routers.bots.BotService") as mock_cls:
        instance = mock_cls.return_value
        instance.update = AsyncMock(return_value=None)

        response = bot_client.put(
            f"/api/v1/bots/{ObjectId()}",
            json={"name": "Pwned"},
            headers=make_auth_header_b(),
        )
    assert response.status_code == 404


@pytest.mark.unit
def test_update_bot_success(bot_client):
    bot_id = str(ObjectId())
    with patch("src.routers.bots.BotService") as mock_cls:
        instance = mock_cls.return_value
        bot = _api_bot(bot_id)
        bot["name"] = "Updated"
        instance.update = AsyncMock(return_value=bot)

        response = bot_client.put(
            f"/api/v1/bots/{bot_id}",
            json={"name": "Updated"},
            headers=make_auth_header(),
        )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated"


@pytest.mark.unit
def test_delete_bot_404_for_cross_tenant(bot_client):
    with patch("src.routers.bots.BotService") as mock_cls:
        instance = mock_cls.return_value
        instance.delete = AsyncMock(return_value=False)

        response = bot_client.delete(f"/api/v1/bots/{ObjectId()}", headers=make_auth_header_b())
    assert response.status_code == 404


@pytest.mark.unit
def test_delete_bot_success(bot_client):
    bot_id = str(ObjectId())
    with patch("src.routers.bots.BotService") as mock_cls:
        instance = mock_cls.return_value
        instance.delete = AsyncMock(return_value=True)

        response = bot_client.delete(f"/api/v1/bots/{bot_id}", headers=make_auth_header())
    assert response.status_code == 200
    assert "deleted" in response.json()["message"].lower()


@pytest.mark.unit
def test_public_bot_endpoint_unauthenticated(bot_client):
    """Public endpoint must NOT require auth — returns minimal config."""
    bot_id = str(ObjectId())
    with patch("src.routers.bots.BotService") as mock_cls:
        instance = mock_cls.return_value
        instance.get_public = AsyncMock(
            return_value={
                "id": bot_id,
                "slug": "support-bot",
                "name": "Support Bot",
                "welcome_message": "Hi!",
                "widget_config": {
                    "primary_color": "#0f172a",
                    "position": "bottom-right",
                    "avatar_url": None,
                },
            }
        )

        response = bot_client.get(f"/api/v1/bots/public/{bot_id}")

    assert response.status_code == 200
    data = response.json()
    # Public response must NOT include secret fields.
    assert "system_prompt" not in data
    assert "tenant_id" not in data
    assert "document_filter" not in data


@pytest.mark.unit
def test_public_bot_404_when_private(bot_client):
    with patch("src.routers.bots.BotService") as mock_cls:
        instance = mock_cls.return_value
        instance.get_public = AsyncMock(return_value=None)

        response = bot_client.get(f"/api/v1/bots/public/{ObjectId()}")
    assert response.status_code == 404


@pytest.mark.unit
def test_public_bot_response_has_strict_allowlist(bot_client):
    """Public route must expose ONLY the safe fields — locked by allowlist.

    Even if the service layer accidentally returns extra keys (regression
    or new field added without the right Pydantic gate), the response
    must still serialize to exactly the documented public surface. Any
    new key added to PublicBotResponse must update this test deliberately.

    The widget_config surface is intentionally cosmetic-only — every field
    listed here is safe to expose to anonymous callers. system_prompt,
    document_filter, tenant_id, etc. must NEVER appear here.
    """
    bot_id = str(ObjectId())
    with patch("src.routers.bots.BotService") as mock_cls:
        instance = mock_cls.return_value
        # Service returns a fully-loaded dict including secret fields.
        # PublicBotResponse must drop everything outside its model.
        instance.get_public = AsyncMock(
            return_value={
                "id": bot_id,
                "slug": "support-bot",
                "name": "Support Bot",
                "welcome_message": "Hi!",
                "widget_config": {
                    "primary_color": "#0f172a",
                    "position": "bottom-right",
                    "avatar_url": None,
                },
                # All of these MUST be filtered out:
                "tenant_id": "tenant-secret",
                "system_prompt": "TOP SECRET PROMPT",
                "document_filter": {"mode": "ids", "document_ids": ["d1"]},
                "tone": "professional",
                "model_config": {"temperature": 0.2, "max_tokens": 1024},
                "is_public": True,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        )

        response = bot_client.get(f"/api/v1/bots/public/{bot_id}")

    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) == {
        "id",
        "slug",
        "name",
        "welcome_message",
        "widget_config",
    }
    # Pinned widget_config surface — the cosmetic theme tokens. Adding a new
    # field to WidgetConfig REQUIRES updating this set deliberately so we
    # consciously check that the field is safe to expose anonymously.
    assert set(data["widget_config"].keys()) == {
        # Existing
        "primary_color",
        "position",
        "avatar_url",
        # Color tokens (#87)
        "color_mode",
        "background",
        "surface",
        "foreground",
        "muted",
        "border",
        "primary_foreground",
        "dark_overrides",
        # Typography (#87)
        "font_family",
        "display_font",
        "base_font_size",
        # Shape & density (#87)
        "radius",
        "density",
        "launcher_shape",
        "launcher_size",
        "panel_size",
        # Branding & icons (#87)
        "launcher_icon",
        "launcher_icon_url",
        "show_avatar_in_messages",
        "branding_text",
    }
