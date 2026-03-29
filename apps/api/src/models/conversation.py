"""Conversation models for chat history."""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Chat message sender role."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    """A single message in a conversation."""

    role: MessageRole = Field(..., description="Message sender role")
    content: str = Field(..., description="Message text content")
    sources: list[str] = Field(
        default_factory=list, description="Document sources cited in this message"
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConversationModel(BaseModel):
    """A chat conversation belonging to a tenant."""

    tenant_id: str = Field(..., description="Tenant this conversation belongs to")
    session_id: str = Field(..., description="Client session identifier")
    messages: list[ChatMessage] = Field(default_factory=list, description="Ordered messages")
    metadata: dict = Field(default_factory=dict, description="Conversation metadata")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
