"""Tests for chat router."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from tests.conftest import MOCK_TENANT_ID, make_auth_header


@pytest.fixture
def app_client():
    """Create test client with mocked deps."""
    from src.main import app

    mock_deps = MagicMock()
    mock_deps.initialize = AsyncMock()
    mock_deps.cleanup = AsyncMock()
    mock_deps.db = MagicMock()
    mock_deps.settings = MagicMock()
    mock_deps.conversations_collection = MagicMock()
    mock_deps.documents_collection = MagicMock()
    mock_deps.chunks_collection = MagicMock()
    # Quota / rate-limit dependencies
    mock_deps.subscriptions_collection = MagicMock()
    mock_deps.subscriptions_collection.find_one = AsyncMock(
        return_value={"plan": "free", "status": "active"}
    )
    mock_deps.usage_collection = MagicMock()
    mock_deps.usage_collection.find_one_and_update = AsyncMock(
        return_value={
            "tenant_id": "test-tenant-001",
            "period_key": "2026-04",
            "queries_count": 1,
        }
    )
    mock_deps.usage_collection.update_one = AsyncMock()
    from src.services.rate_limit import reset_default_limiter

    reset_default_limiter()

    with TestClient(app) as c:
        app.state.deps = mock_deps  # Override after lifespan runs
        yield c, mock_deps


@pytest.mark.unit
def test_chat_missing_auth_header(app_client):
    """Chat without Authorization header returns 401."""
    client, _ = app_client
    response = client.post(
        "/api/v1/chat",
        json={"message": "Hello"},
    )
    assert response.status_code == 401


@pytest.mark.unit
def test_chat_empty_message(app_client):
    """Chat with empty message returns 422."""
    client, _ = app_client
    response = client.post(
        "/api/v1/chat",
        json={"message": ""},
        headers=make_auth_header(),
    )
    assert response.status_code == 422


@pytest.mark.unit
def test_chat_valid_request_returns_response(app_client):
    """Chat with valid request returns answer and conversation_id."""
    client, mock_deps = app_client

    mock_result = {
        "answer": "Here is the answer.",
        "sources": [],
        "conversation_id": "conv-123",
    }

    with patch("src.routers.chat.ChatService") as mock_chat_cls:
        mock_chat = MagicMock()
        mock_chat.handle_message = AsyncMock(return_value=mock_result)
        mock_chat_cls.return_value = mock_chat

        response = client.post(
            "/api/v1/chat",
            json={"message": "How do I configure SSO?"},
            headers=make_auth_header(),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Here is the answer."
        assert data["conversation_id"] == "conv-123"


@pytest.mark.unit
def test_chat_request_threads_bot_id_to_service(app_client):
    """The router must forward body.bot_id to ChatService.handle_message."""
    client, _ = app_client

    captured: dict = {}

    with patch("src.routers.chat.ChatService") as mock_chat_cls:
        mock_chat = MagicMock()

        async def fake_handle(**kwargs):
            captured.update(kwargs)
            return {
                "answer": "ok",
                "sources": [],
                "citations": [],
                "conversation_id": "conv-1",
                "rewritten_queries": [],
            }

        mock_chat.handle_message = AsyncMock(side_effect=fake_handle)
        mock_chat_cls.return_value = mock_chat

        response = client.post(
            "/api/v1/chat",
            json={"message": "hi", "bot_id": "650000000000000000000001"},
            headers=make_auth_header(),
        )

    assert response.status_code == 200
    assert captured.get("bot_id") == "650000000000000000000001"


@pytest.mark.unit
def test_chat_returns_404_for_unknown_bot_id(app_client):
    """Unresolvable bot_id (cross-tenant or unknown) maps to 404."""
    client, _ = app_client

    with patch("src.routers.chat.ChatService") as mock_chat_cls:
        mock_chat = MagicMock()
        from src.services.chat import BotNotFoundError

        mock_chat.handle_message = AsyncMock(side_effect=BotNotFoundError("no"))
        mock_chat_cls.return_value = mock_chat

        response = client.post(
            "/api/v1/chat",
            json={"message": "hi", "bot_id": "650000000000000000000001"},
            headers=make_auth_header(),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Bot not found"


@pytest.mark.unit
def test_chat_conversation_not_found(app_client):
    """Chat with nonexistent conversation_id returns 404."""
    client, mock_deps = app_client

    with patch("src.routers.chat.ChatService") as mock_chat_cls:
        mock_chat = MagicMock()
        from src.services.chat import ConversationNotFoundError

        mock_chat.handle_message = AsyncMock(
            side_effect=ConversationNotFoundError("Conversation not found")
        )
        mock_chat_cls.return_value = mock_chat

        response = client.post(
            "/api/v1/chat",
            json={"message": "Hello", "conversation_id": "nonexistent"},
            headers=make_auth_header(),
        )

        assert response.status_code == 404


# --- WebSocket ticket-based authentication tests ---


@pytest.mark.unit
def test_websocket_rejects_missing_ticket(client):
    """WebSocket without ticket query param is rejected with code 4001."""
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/v1/chat/ws"):
            pass
    assert exc_info.value.code == 4001


@pytest.mark.unit
def test_websocket_rejects_invalid_ticket(client, mock_deps):
    """WebSocket with invalid ticket is rejected with code 4001."""
    from starlette.websockets import WebSocketDisconnect

    # Mock ws_tickets_collection for consume_ticket lookup
    mock_ws_tickets = MagicMock()
    mock_ws_tickets.find_one_and_update = AsyncMock(return_value=None)
    mock_deps.ws_tickets_collection = mock_ws_tickets

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/v1/chat/ws?ticket=invalid-ticket"):
            pass
    assert exc_info.value.code == 4001


@pytest.mark.unit
def test_websocket_accepts_valid_ticket(client, mock_deps):
    """WebSocket with valid ticket is accepted and resolves tenant."""
    # Mock ws_tickets_collection to return a valid ticket doc
    mock_ws_tickets = MagicMock()
    mock_ws_tickets.find_one_and_update = AsyncMock(
        return_value={"tenant_id": MOCK_TENANT_ID, "ticket_hash": "abc123"}
    )
    mock_deps.ws_tickets_collection = mock_ws_tickets
    mock_deps.settings = MagicMock()

    with client.websocket_connect("/api/v1/chat/ws?ticket=valid-ticket") as ws:
        ws.send_json({"type": "cancel"})
        response = ws.receive_json()
        assert response["type"] == "cancelled"
