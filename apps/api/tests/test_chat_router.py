"""Tests for chat router."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt

from tests.conftest import JWT_SECRET, MOCK_TENANT_ID, make_auth_header


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


# --- WebSocket authentication tests ---


def _make_ws_token(tenant_id: str = MOCK_TENANT_ID) -> str:
    """Create a JWT token for WebSocket auth."""
    return jose_jwt.encode(
        {"sub": "test-user", "tenant_id": tenant_id, "role": "owner"},
        JWT_SECRET,
        algorithm="HS256",
    )


@pytest.mark.unit
def test_websocket_rejects_missing_token(client):
    """WebSocket without token query param is rejected with code 4001."""
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/v1/chat/ws"):
            pass
    assert exc_info.value.code == 4001


@pytest.mark.unit
def test_websocket_rejects_invalid_token(client):
    """WebSocket with invalid token is rejected with code 4001."""
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/v1/chat/ws?token=invalid-jwt"):
            pass
    assert exc_info.value.code == 4001


@pytest.mark.unit
def test_websocket_rejects_no_tenant_in_token(client):
    """WebSocket with JWT missing tenant_id claim is rejected with code 4001."""
    from starlette.websockets import WebSocketDisconnect

    token = jose_jwt.encode({"sub": "test-user"}, JWT_SECRET, algorithm="HS256")
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/api/v1/chat/ws?token={token}"):
            pass
    assert exc_info.value.code == 4001


@pytest.mark.unit
def test_websocket_accepts_valid_jwt(client, mock_deps):
    """WebSocket with valid JWT token is accepted."""
    token = _make_ws_token()
    mock_deps.settings = MagicMock()

    with client.websocket_connect(f"/api/v1/chat/ws?token={token}") as ws:
        ws.send_json({"type": "cancel"})
        response = ws.receive_json()
        assert response["type"] == "cancelled"
