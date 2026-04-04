"""Tests for WebSocket ticket service and endpoint."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import MOCK_TENANT_ID, make_auth_header


@pytest.mark.unit
async def test_create_ticket_stores_tenant_id():
    """create_ticket stores tenant_id in the ticket document."""
    from src.services.ws_ticket import WSTicketService

    mock_collection = MagicMock()
    mock_collection.insert_one = AsyncMock()

    service = WSTicketService(mock_collection)
    ticket = await service.create_ticket(MOCK_TENANT_ID)

    assert ticket  # Non-empty string
    inserted = mock_collection.insert_one.call_args[0][0]
    assert inserted["tenant_id"] == MOCK_TENANT_ID
    assert inserted["used"] is False
    assert "ticket_hash" in inserted
    assert "expires_at" in inserted


@pytest.mark.unit
async def test_consume_ticket_returns_tenant_id():
    """consume_ticket returns tenant_id for valid ticket."""
    from src.services.ws_ticket import WSTicketService

    mock_collection = MagicMock()
    mock_collection.find_one_and_update = AsyncMock(
        return_value={"tenant_id": MOCK_TENANT_ID, "ticket_hash": "abc"}
    )

    service = WSTicketService(mock_collection)
    result = await service.consume_ticket("some-ticket")

    assert result == MOCK_TENANT_ID
    # Verify it atomically marks as used
    call_args = mock_collection.find_one_and_update.call_args
    assert call_args[0][1] == {"$set": {"used": True}}


@pytest.mark.unit
async def test_consume_ticket_returns_none_for_invalid():
    """consume_ticket returns None for invalid/expired/used ticket."""
    from src.services.ws_ticket import WSTicketService

    mock_collection = MagicMock()
    mock_collection.find_one_and_update = AsyncMock(return_value=None)

    service = WSTicketService(mock_collection)
    result = await service.consume_ticket("invalid-ticket")

    assert result is None


@pytest.mark.unit
def test_ws_ticket_endpoint_requires_auth(client):
    """POST /api/v1/auth/ws-ticket requires authentication."""
    response = client.post("/api/v1/auth/ws-ticket")
    assert response.status_code == 401


@pytest.mark.unit
def test_ws_ticket_endpoint_returns_ticket(client, mock_deps):
    """POST /api/v1/auth/ws-ticket returns a ticket for authenticated user."""
    mock_ws_tickets = MagicMock()
    mock_ws_tickets.insert_one = AsyncMock()
    mock_deps.ws_tickets_collection = mock_ws_tickets

    response = client.post(
        "/api/v1/auth/ws-ticket",
        headers=make_auth_header(),
    )

    assert response.status_code == 200
    data = response.json()
    assert "ticket" in data
    assert len(data["ticket"]) > 0
