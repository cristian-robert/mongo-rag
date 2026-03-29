"""Request and response models for API endpoints."""

from typing import Optional

from pydantic import BaseModel, Field


# --- Ingestion ---

class IngestResponse(BaseModel):
    """Response from document ingestion endpoint."""
    document_id: str = Field(..., description="MongoDB document ID")
    status: str = Field(..., description="Processing status")
    task_id: str = Field(..., description="Celery task ID for tracking")


class DocumentStatusResponse(BaseModel):
    """Response from document status endpoint."""
    document_id: str
    status: str
    chunk_count: int = 0
    version: int = 1
    error_message: Optional[str] = None


# --- Chat ---

class ChatRequest(BaseModel):
    """Request body for chat endpoint."""
    message: str = Field(..., min_length=1, max_length=10000, description="User message")
    conversation_id: Optional[str] = Field(default=None, description="Existing conversation ID")
    search_type: str = Field(default="hybrid", description="Search type: semantic, text, hybrid")


class SourceReference(BaseModel):
    """A source document referenced in a chat response."""
    document_title: str
    heading_path: list[str] = Field(default_factory=list)
    snippet: str


class ChatResponse(BaseModel):
    """Response from chat endpoint (non-streaming)."""
    answer: str
    sources: list[SourceReference] = Field(default_factory=list)
    conversation_id: str


# --- WebSocket ---

class WSMessage(BaseModel):
    """Incoming WebSocket message from client."""
    type: str = Field(..., description="Message type: message, cancel")
    content: Optional[str] = Field(default=None, description="Message content")
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID")
