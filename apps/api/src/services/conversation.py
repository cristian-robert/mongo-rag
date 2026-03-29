"""Conversation CRUD service."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pymongo.asynchronous.collection import AsyncCollection

from src.models.conversation import ChatMessage

logger = logging.getLogger(__name__)


class ConversationService:
    """Manages conversation persistence in MongoDB."""

    def __init__(self, collection: AsyncCollection) -> None:
        self.collection = collection

    async def get_or_create(
        self,
        tenant_id: str,
        conversation_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Get existing conversation or create a new one.

        Args:
            tenant_id: Tenant ID for isolation.
            conversation_id: Existing conversation ID, or None to create new.

        Returns:
            Conversation document dict, or None if conversation_id provided
            but not found for this tenant (cross-tenant access attempt).
        """
        if conversation_id:
            conv = await self.collection.find_one(
                {"_id": conversation_id, "tenant_id": tenant_id}
            )
            if conv is None:
                return None
            return conv

        now = datetime.now(timezone.utc)
        new_conv = {
            "_id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "session_id": str(uuid.uuid4()),
            "messages": [],
            "metadata": {},
            "created_at": now,
            "updated_at": now,
        }
        await self.collection.insert_one(new_conv)
        return new_conv

    async def append_message(
        self, conversation_id: str, tenant_id: str, message: ChatMessage
    ) -> None:
        """Append a message to a conversation.

        Args:
            conversation_id: Conversation to append to.
            tenant_id: Tenant ID for isolation.
            message: ChatMessage to append.
        """
        await self.collection.update_one(
            {"_id": conversation_id, "tenant_id": tenant_id},
            {
                "$push": {"messages": message.model_dump(mode="json")},
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
        )

    async def get_history(
        self, conversation_id: str, tenant_id: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get recent messages from a conversation.

        Args:
            conversation_id: Conversation to fetch from.
            tenant_id: Tenant ID for isolation.
            limit: Max number of recent messages to return.

        Returns:
            List of message dicts (most recent last), empty if not found.
        """
        conv = await self.collection.find_one(
            {"_id": conversation_id, "tenant_id": tenant_id}
        )
        if not conv:
            return []
        messages = conv.get("messages", [])
        return messages[-limit:]
