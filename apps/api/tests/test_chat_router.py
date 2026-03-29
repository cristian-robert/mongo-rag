"""Tests for chat router."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

MOCK_TENANT_ID = "test-tenant-001"


@pytest.fixture
def app_client():
    """Create test client with mocked deps."""
    with patch("src.main._deps") as mock_deps:
        mock_deps.initialize = AsyncMock()
        mock_deps.cleanup = AsyncMock()
        mock_deps.db = MagicMock()
        mock_deps.settings = MagicMock()
        mock_deps.conversations_collection = MagicMock()
        mock_deps.documents_collection = MagicMock()
        mock_deps.chunks_collection = MagicMock()

        from src.main import app
        with TestClient(app) as c:
            yield c, mock_deps


@pytest.mark.unit
def test_chat_missing_tenant_header(app_client):
    """Chat without X-Tenant-ID returns 400."""
    client, _ = app_client
    response = client.post(
        "/api/v1/chat",
        json={"message": "Hello"},
    )
    assert response.status_code == 400


@pytest.mark.unit
def test_chat_empty_message(app_client):
    """Chat with empty message returns 422."""
    client, _ = app_client
    response = client.post(
        "/api/v1/chat",
        json={"message": ""},
        headers={"X-Tenant-ID": MOCK_TENANT_ID},
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
            headers={"X-Tenant-ID": MOCK_TENANT_ID},
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
        mock_chat.handle_message = AsyncMock(side_effect=ValueError("Conversation not found"))
        mock_chat_cls.return_value = mock_chat

        response = client.post(
            "/api/v1/chat",
            json={"message": "Hello", "conversation_id": "nonexistent"},
            headers={"X-Tenant-ID": MOCK_TENANT_ID},
        )

        assert response.status_code == 404
