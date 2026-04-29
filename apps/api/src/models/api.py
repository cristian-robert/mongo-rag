"""Request and response models for API endpoints."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

# --- Ingestion ---


class IngestResponse(BaseModel):
    """Response from document ingestion endpoint."""

    document_id: str = Field(..., description="MongoDB document ID")
    status: str = Field(..., description="Processing status")
    task_id: str = Field(..., description="Celery task ID for tracking")


class IngestURLRequest(BaseModel):
    """Request body for URL-based document ingestion."""

    url: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="HTTP(S) URL to fetch and ingest",
    )
    title: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Override document title (defaults to <title> or hostname/path)",
    )
    metadata: Optional[dict] = Field(
        default=None,
        description="Optional caller-supplied metadata (merged onto extracted metadata)",
    )

    @field_validator("url")
    @classmethod
    def validate_url_scheme(cls, v: str) -> str:
        """Surface scheme errors as Pydantic validation errors (422)."""
        from urllib.parse import urlparse

        parsed = urlparse(v.strip())
        if parsed.scheme.lower() not in {"http", "https"}:
            raise ValueError("URL must use http or https scheme")
        if not parsed.hostname:
            raise ValueError("URL must include a hostname")
        return v.strip()


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
    search_type: Literal["semantic", "text", "hybrid"] = Field(
        default="hybrid", description="Search type: semantic, text, hybrid"
    )


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


# --- Auth ---


class SignupRequest(BaseModel):
    """Request body for user signup."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=128, description="Password")
    organization_name: str = Field(
        ..., min_length=2, max_length=100, description="Organization name"
    )


class SignupResponse(BaseModel):
    """Response from signup endpoint."""

    user_id: str
    tenant_id: str
    email: str


class LoginRequest(BaseModel):
    """Request body for user login."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=1, description="Password")


class LoginResponse(BaseModel):
    """Response from login endpoint (user data for Auth.js)."""

    user_id: str
    tenant_id: str
    email: str
    name: str
    role: str


class ForgotPasswordRequest(BaseModel):
    """Request body for forgot password."""

    email: EmailStr = Field(..., description="User email address")


class ResetPasswordRequest(BaseModel):
    """Request body for password reset."""

    token: str = Field(..., min_length=1, description="Reset token from email")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


class WSTicketResponse(BaseModel):
    """Response containing a short-lived WebSocket ticket."""

    ticket: str


# --- API Keys ---


VALID_PERMISSIONS = {"chat", "search"}


class CreateKeyRequest(BaseModel):
    """Request body for creating an API key."""

    name: str = Field(..., min_length=2, max_length=100, description="Human-readable key name")
    permissions: list[str] = Field(
        default_factory=lambda: ["chat", "search"],
        description="Allowed operations",
    )

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v: list[str]) -> list[str]:
        """Ensure all permissions are from the known set."""
        invalid = set(v) - VALID_PERMISSIONS
        if invalid:
            raise ValueError(f"Invalid permissions: {', '.join(sorted(invalid))}")
        return v


class CreateKeyResponse(BaseModel):
    """Response from key creation (raw key shown once)."""

    raw_key: str = Field(..., description="Full API key — shown only once")
    key_prefix: str = Field(..., description="First 8 chars for identification")
    name: str
    permissions: list[str]
    created_at: datetime


class KeyResponse(BaseModel):
    """A single API key's metadata (no raw key or hash)."""

    id: str = Field(..., description="Key document ID")
    key_prefix: str = Field(..., description="First 8 chars for identification")
    name: str
    permissions: list[str]
    is_revoked: bool
    last_used_at: Optional[datetime] = None
    created_at: datetime


class KeyListResponse(BaseModel):
    """List of API keys for a tenant."""

    keys: list[KeyResponse]
