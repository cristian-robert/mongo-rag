"""WebSocket ticket service — short-lived, one-time-use tickets.

Clients exchange a JWT or API key for a ticket via REST, then connect
to WebSocket with ?ticket=<ticket>. This avoids exposing long-lived
credentials in the URL (which leaks into logs, browser history, etc.).
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from pymongo.asynchronous.collection import AsyncCollection

logger = logging.getLogger(__name__)

# Tickets expire after 30 seconds — just enough to complete the WS handshake.
_TICKET_TTL_SECONDS = 30


class WSTicketService:
    """Issue and consume one-time WebSocket tickets."""

    def __init__(self, collection: AsyncCollection) -> None:
        self._tickets = collection

    async def create_ticket(self, tenant_id: str) -> str:
        """Create a short-lived ticket for the given tenant.

        Args:
            tenant_id: The authenticated tenant's ID.

        Returns:
            Raw ticket string (sent to client, never stored).
        """
        raw_ticket = secrets.token_urlsafe(32)
        ticket_hash = hashlib.sha256(raw_ticket.encode()).hexdigest()
        now = datetime.now(timezone.utc)

        await self._tickets.insert_one(
            {
                "ticket_hash": ticket_hash,
                "tenant_id": tenant_id,
                "expires_at": now + timedelta(seconds=_TICKET_TTL_SECONDS),
                "used": False,
                "created_at": now,
            }
        )

        return raw_ticket

    async def consume_ticket(self, raw_ticket: str) -> Optional[str]:
        """Validate and consume a one-time ticket.

        Atomically marks the ticket as used so it cannot be reused.

        Args:
            raw_ticket: The raw ticket string from the client.

        Returns:
            tenant_id if valid, None if invalid/expired/already used.
        """
        ticket_hash = hashlib.sha256(raw_ticket.encode()).hexdigest()
        now = datetime.now(timezone.utc)

        doc = await self._tickets.find_one_and_update(
            {
                "ticket_hash": ticket_hash,
                "used": False,
                "expires_at": {"$gt": now},
            },
            {"$set": {"used": True}},
        )

        if not doc:
            return None

        return doc["tenant_id"]
