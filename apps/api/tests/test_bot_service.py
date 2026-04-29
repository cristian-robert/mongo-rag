"""Unit tests for the bot service."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from src.models.bot import CreateBotRequest, UpdateBotRequest
from src.services.bot import BotService, BotSlugTakenError


def _valid_payload(slug: str = "support-bot") -> dict:
    return {
        "name": "Support Bot",
        "slug": slug,
        "description": "Answers customer questions",
        "system_prompt": "You are a helpful support assistant for ACME.",
        "welcome_message": "How can I help?",
        "tone": "friendly",
        "is_public": True,
    }


@pytest.fixture
def mock_bots_collection():
    coll = MagicMock()
    coll.insert_one = AsyncMock()
    coll.find = MagicMock()
    coll.find_one = AsyncMock(return_value=None)
    coll.find_one_and_update = AsyncMock(return_value=None)
    coll.delete_one = AsyncMock()
    coll.count_documents = AsyncMock(return_value=0)
    return coll


@pytest.mark.unit
async def test_create_bot_persists_tenant_id_and_returns_response(mock_bots_collection):
    inserted_id = ObjectId()
    mock_bots_collection.insert_one.return_value = MagicMock(inserted_id=inserted_id)

    service = BotService(mock_bots_collection)
    body = CreateBotRequest(**_valid_payload())

    result = await service.create("tenant-abc", body)

    mock_bots_collection.insert_one.assert_awaited_once()
    stored = mock_bots_collection.insert_one.call_args[0][0]
    assert stored["tenant_id"] == "tenant-abc"
    assert stored["slug"] == "support-bot"
    assert "model_config_" in stored
    assert result["id"] == str(inserted_id)
    assert result["tenant_id"] == "tenant-abc"
    assert result["is_public"] is True


@pytest.mark.unit
async def test_create_bot_raises_on_slug_collision(mock_bots_collection):
    mock_bots_collection.insert_one.side_effect = DuplicateKeyError("dup")
    service = BotService(mock_bots_collection)
    body = CreateBotRequest(**_valid_payload())

    with pytest.raises(BotSlugTakenError):
        await service.create("tenant-abc", body)


@pytest.mark.unit
async def test_get_bot_filters_by_tenant(mock_bots_collection):
    oid = ObjectId()
    now = datetime.now(timezone.utc)
    mock_bots_collection.find_one.return_value = {
        "_id": oid,
        "tenant_id": "tenant-abc",
        "name": "Support Bot",
        "slug": "support-bot",
        "description": None,
        "system_prompt": "You are helpful",
        "welcome_message": "Hi!",
        "tone": "professional",
        "is_public": False,
        "model_config_": {"temperature": 0.2, "max_tokens": 1024},
        "widget_config": {
            "primary_color": "#0f172a",
            "position": "bottom-right",
            "avatar_url": None,
        },
        "document_filter": {"mode": "all", "document_ids": []},
        "created_at": now,
        "updated_at": now,
    }
    service = BotService(mock_bots_collection)

    result = await service.get(str(oid), "tenant-abc")

    mock_bots_collection.find_one.assert_awaited_once_with({"_id": oid, "tenant_id": "tenant-abc"})
    assert result is not None
    assert result["id"] == str(oid)


@pytest.mark.unit
async def test_get_bot_returns_none_for_invalid_oid(mock_bots_collection):
    service = BotService(mock_bots_collection)
    result = await service.get("not-an-oid", "tenant-abc")
    assert result is None
    mock_bots_collection.find_one.assert_not_awaited()


@pytest.mark.unit
async def test_get_bot_returns_none_for_cross_tenant(mock_bots_collection):
    mock_bots_collection.find_one.return_value = None
    service = BotService(mock_bots_collection)
    result = await service.get(str(ObjectId()), "other-tenant")
    assert result is None


@pytest.mark.unit
async def test_update_bot_filters_by_tenant_and_excludes_none(mock_bots_collection):
    oid = ObjectId()
    now = datetime.now(timezone.utc)
    mock_bots_collection.find_one_and_update.return_value = {
        "_id": oid,
        "tenant_id": "tenant-abc",
        "name": "Updated",
        "slug": "support-bot",
        "description": None,
        "system_prompt": "You are helpful",
        "welcome_message": "Hi!",
        "tone": "professional",
        "is_public": False,
        "model_config_": {"temperature": 0.5, "max_tokens": 1024},
        "widget_config": {
            "primary_color": "#0f172a",
            "position": "bottom-right",
            "avatar_url": None,
        },
        "document_filter": {"mode": "all", "document_ids": []},
        "created_at": now,
        "updated_at": now,
    }
    service = BotService(mock_bots_collection)

    result = await service.update(
        str(oid),
        "tenant-abc",
        UpdateBotRequest(name="Updated"),
    )

    args, kwargs = mock_bots_collection.find_one_and_update.call_args
    assert args[0] == {"_id": oid, "tenant_id": "tenant-abc"}
    update = args[1]["$set"]
    assert update["name"] == "Updated"
    # None-valued fields must not overwrite stored values.
    assert "description" not in update
    assert "tone" not in update
    assert result is not None and result["name"] == "Updated"


@pytest.mark.unit
async def test_update_bot_returns_none_for_cross_tenant(mock_bots_collection):
    mock_bots_collection.find_one_and_update.return_value = None
    service = BotService(mock_bots_collection)
    result = await service.update(str(ObjectId()), "wrong-tenant", UpdateBotRequest(name="xy"))
    assert result is None


@pytest.mark.unit
async def test_delete_bot_filters_by_tenant(mock_bots_collection):
    oid = ObjectId()
    mock_bots_collection.delete_one.return_value = MagicMock(deleted_count=1)
    service = BotService(mock_bots_collection)

    ok = await service.delete(str(oid), "tenant-abc")
    mock_bots_collection.delete_one.assert_awaited_once_with(
        {"_id": oid, "tenant_id": "tenant-abc"}
    )
    assert ok is True


@pytest.mark.unit
async def test_delete_bot_returns_false_when_not_found(mock_bots_collection):
    mock_bots_collection.delete_one.return_value = MagicMock(deleted_count=0)
    service = BotService(mock_bots_collection)
    ok = await service.delete(str(ObjectId()), "tenant-abc")
    assert ok is False


@pytest.mark.unit
async def test_get_public_only_returns_public_bots(mock_bots_collection):
    oid = ObjectId()
    mock_bots_collection.find_one.return_value = None
    service = BotService(mock_bots_collection)
    result = await service.get_public(str(oid))

    mock_bots_collection.find_one.assert_awaited_once_with({"_id": oid, "is_public": True})
    assert result is None


@pytest.mark.unit
async def test_get_public_omits_secret_fields(mock_bots_collection):
    oid = ObjectId()
    mock_bots_collection.find_one.return_value = {
        "_id": oid,
        "tenant_id": "secret-tenant",
        "name": "Bot",
        "slug": "bot",
        "system_prompt": "TOP SECRET PROMPT",
        "welcome_message": "Hi",
        "is_public": True,
        "widget_config": {"primary_color": "#fff", "position": "bottom-right", "avatar_url": None},
        "document_filter": {"mode": "ids", "document_ids": ["d1", "d2"]},
    }
    service = BotService(mock_bots_collection)

    result = await service.get_public(str(oid))
    assert result is not None
    assert "system_prompt" not in result
    assert "tenant_id" not in result
    assert "document_filter" not in result
    assert result["welcome_message"] == "Hi"


@pytest.mark.unit
async def test_list_for_tenant_filters(mock_bots_collection):
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.to_list = AsyncMock(return_value=[])
    mock_bots_collection.find.return_value = cursor
    service = BotService(mock_bots_collection)

    await service.list_for_tenant("tenant-abc")
    mock_bots_collection.find.assert_called_once_with({"tenant_id": "tenant-abc"})
    cursor.sort.assert_called_once_with("created_at", -1)
