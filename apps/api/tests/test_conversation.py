"""Tests for conversation service."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.conversation import ChatMessage, MessageRole


@pytest.mark.unit
async def test_get_or_create_new_conversation():
    """Creates a new conversation when no conversation_id is provided."""
    from src.services.conversation import ConversationService

    mock_collection = MagicMock()
    mock_collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id="new-conv-id"))

    service = ConversationService(mock_collection)
    conv = await service.get_or_create("tenant-1", conversation_id=None)

    assert conv["tenant_id"] == "tenant-1"
    assert "session_id" in conv
    mock_collection.insert_one.assert_called_once()


@pytest.mark.unit
async def test_get_or_create_existing_conversation():
    """Returns existing conversation when conversation_id is provided and matches tenant."""
    from src.services.conversation import ConversationService

    existing = {
        "_id": "existing-conv-id",
        "tenant_id": "tenant-1",
        "session_id": "sess-123",
        "messages": [],
    }
    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(return_value=existing)

    service = ConversationService(mock_collection)
    conv = await service.get_or_create("tenant-1", conversation_id="existing-conv-id")

    assert conv["_id"] == "existing-conv-id"
    mock_collection.find_one.assert_called_once()


@pytest.mark.unit
async def test_get_or_create_wrong_tenant_returns_none():
    """Returns None when conversation_id exists but belongs to different tenant."""
    from src.services.conversation import ConversationService

    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(return_value=None)  # Filtered by tenant_id

    service = ConversationService(mock_collection)
    conv = await service.get_or_create("tenant-2", conversation_id="other-tenant-conv")

    assert conv is None


@pytest.mark.unit
async def test_append_message():
    """Appends a message to a conversation."""
    from src.services.conversation import ConversationService

    mock_collection = MagicMock()
    mock_collection.update_one = AsyncMock()

    service = ConversationService(mock_collection)
    message = ChatMessage(role=MessageRole.USER, content="Hello")

    await service.append_message("conv-1", "tenant-1", message)

    mock_collection.update_one.assert_called_once()
    call_args = mock_collection.update_one.call_args
    assert call_args[0][0] == {"_id": "conv-1", "tenant_id": "tenant-1"}


@pytest.mark.unit
async def test_get_history():
    """Retrieves last N messages from a conversation."""
    from src.services.conversation import ConversationService

    messages = [
        {"role": "user", "content": "msg1", "sources": [], "timestamp": "2026-01-01T00:00:00Z"},
        {
            "role": "assistant",
            "content": "msg2",
            "sources": [],
            "timestamp": "2026-01-01T00:01:00Z",
        },
    ]
    existing = {"_id": "conv-1", "tenant_id": "t1", "messages": messages}

    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(return_value=existing)

    service = ConversationService(mock_collection)
    history = await service.get_history("conv-1", "t1", limit=10)

    assert len(history) == 2
    assert history[0]["content"] == "msg1"
