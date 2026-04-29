"""Request and response models for API endpoints."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class StrictRequest(BaseModel):
    """Base for request bodies — rejects unknown fields and strips whitespace.

    Forbidding extra fields prevents mass-assignment style bugs where a
    client passes fields the model author did not intend to accept.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


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


# --- Document CRUD ---


class DocumentRecord(BaseModel):
    """A single document as returned by CRUD endpoints (no content/embeddings)."""

    document_id: str
    title: str
    source: str
    status: str
    chunk_count: int = 0
    format: str = ""
    size_bytes: Optional[int] = None
    metadata: dict = Field(default_factory=dict)
    version: int = 1
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    """Paginated document listing."""

    items: list[DocumentRecord]
    total: int
    page: int
    page_size: int


class DocumentUpdateRequest(BaseModel):
    """PATCH body for updating user-editable document metadata."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    metadata: Optional[dict] = Field(default=None, description="Replace metadata dict wholesale")

    @field_validator("metadata")
    @classmethod
    def metadata_must_be_dict(cls, v: Optional[dict]) -> Optional[dict]:
        if v is None:
            return v
        if not isinstance(v, dict):
            raise ValueError("metadata must be a JSON object")
        return v


class BulkDeleteRequest(BaseModel):
    """Body for bulk delete: {ids: [...]}."""

    ids: list[str] = Field(..., min_length=1, max_length=100)

    @field_validator("ids")
    @classmethod
    def ids_must_be_unique_nonempty(cls, v: list[str]) -> list[str]:
        if any(not isinstance(i, str) or not i.strip() for i in v):
            raise ValueError("ids must be non-empty strings")
        return list({i for i in v})  # de-dupe


class BulkDeleteResponse(BaseModel):
    """Result of a bulk delete operation."""

    requested: int
    deleted: int


class ReingestResponse(BaseModel):
    """Response from re-ingestion trigger."""

    document_id: str
    status: str


# --- Chat ---


class RetrievalConfig(BaseModel):
    """Per-request retrieval tuning. Optional — defaults preserve existing behavior."""

    match_count: Optional[int] = Field(
        default=None, ge=1, le=50, description="Top-k chunks (default from settings)."
    )
    rrf_k: Optional[int] = Field(
        default=None, ge=1, le=200, description="RRF constant (default 60)."
    )
    rerank: Optional[bool] = Field(
        default=None, description="Override reranker enabled flag for this request."
    )
    rerank_top_n: Optional[int] = Field(
        default=None, ge=1, le=50, description="Number of candidates to feed the reranker."
    )
    query_rewrite: Optional[bool] = Field(
        default=None, description="Override query rewriting flag for this request."
    )


class ChatRequest(StrictRequest):
    """Request body for chat endpoint."""

    message: str = Field(..., min_length=1, max_length=10000, description="User message")
    conversation_id: Optional[str] = Field(
        default=None, max_length=128, description="Existing conversation ID"
    )
    search_type: Literal["semantic", "text", "hybrid"] = Field(
        default="hybrid", description="Search type: semantic, text, hybrid"
    )
    retrieval: Optional[RetrievalConfig] = Field(
        default=None, description="Optional per-request retrieval tuning."
    )


class SourceReference(BaseModel):
    """A source document referenced in a chat response."""

    document_title: str
    heading_path: list[str] = Field(default_factory=list)
    snippet: str


class Citation(BaseModel):
    """A numbered inline citation extracted from the assistant's answer.

    ``marker`` is the integer used in the answer text (e.g. ``[1]``).
    ``relevance_score`` is the post-rerank score when reranking is enabled,
    otherwise the upstream RRF/vector/text score.
    """

    marker: int = Field(..., ge=1, description="Citation marker number used in the answer.")
    chunk_id: str
    document_id: str
    document_title: str
    document_source: str
    heading_path: list[str] = Field(default_factory=list)
    snippet: str
    relevance_score: float
    page_number: Optional[int] = None


class ChatResponse(BaseModel):
    """Response from chat endpoint (non-streaming)."""

    answer: str
    sources: list[SourceReference] = Field(default_factory=list)
    citations: list[Citation] = Field(
        default_factory=list,
        description="Inline citations resolved from [n] markers in the answer.",
    )
    conversation_id: str
    rewritten_queries: list[str] = Field(
        default_factory=list,
        description="Additional retrieval queries derived from the user message (debug/eval).",
    )


# --- WebSocket ---


class WSMessage(StrictRequest):
    """Incoming WebSocket message from client."""

    type: Literal["message", "cancel"] = Field(..., description="Message type: message or cancel")
    content: Optional[str] = Field(default=None, max_length=10000, description="Message content")
    conversation_id: Optional[str] = Field(
        default=None, max_length=128, description="Conversation ID"
    )


# --- Auth ---


class SignupRequest(StrictRequest):
    """Request body for user signup."""

    email: EmailStr = Field(..., max_length=320, description="User email address")
    password: str = Field(..., min_length=8, max_length=128, description="Password")
    organization_name: str = Field(
        ..., min_length=2, max_length=100, description="Organization name"
    )


class SignupResponse(BaseModel):
    """Response from signup endpoint."""

    user_id: str
    tenant_id: str
    email: str


class LoginRequest(StrictRequest):
    """Request body for user login."""

    email: EmailStr = Field(..., max_length=320, description="User email address")
    password: str = Field(..., min_length=1, max_length=128, description="Password")


class LoginResponse(BaseModel):
    """Response from login endpoint (user data for Auth.js)."""

    user_id: str
    tenant_id: str
    email: str
    name: str
    role: str


class ForgotPasswordRequest(StrictRequest):
    """Request body for forgot password."""

    email: EmailStr = Field(..., max_length=320, description="User email address")


class ResetPasswordRequest(StrictRequest):
    """Request body for password reset."""

    token: str = Field(..., min_length=1, max_length=512, description="Reset token from email")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


class WSTicketResponse(BaseModel):
    """Response containing a short-lived WebSocket ticket."""

    ticket: str


# --- API Keys ---


VALID_PERMISSIONS = {"chat", "search"}


class CreateKeyRequest(StrictRequest):
    """Request body for creating an API key."""

    name: str = Field(..., min_length=2, max_length=100, description="Human-readable key name")
    permissions: list[str] = Field(
        default_factory=lambda: ["chat", "search"],
        max_length=8,
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


# --- Team / RBAC ---


TeamRole = Literal["owner", "admin", "member", "viewer"]


class MemberResponse(BaseModel):
    """A team member as exposed to the dashboard."""

    id: str
    email: str
    name: str
    role: TeamRole
    is_active: bool
    created_at: datetime


class MemberListResponse(BaseModel):
    members: list[MemberResponse]


class UpdateMemberRoleRequest(BaseModel):
    role: TeamRole = Field(..., description="New role for the member")


class InvitationResponse(BaseModel):
    """A pending or historical invitation."""

    id: str
    email: str
    role: TeamRole
    expires_at: datetime
    accepted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    created_at: datetime


class InvitationListResponse(BaseModel):
    invitations: list[InvitationResponse]


class CreateInvitationRequest(BaseModel):
    email: EmailStr
    role: TeamRole = Field(default="member")


class CreateInvitationResponse(BaseModel):
    invitation: InvitationResponse
    accept_url: str = Field(..., description="One-time invite link — shown once")


class AcceptInvitationRequest(BaseModel):
    """Used by an already-authenticated user to accept their invite."""

    token: str = Field(..., min_length=10)


class AcceptInvitationSignupRequest(BaseModel):
    """Used by a new user to sign up and accept an invite atomically."""

    token: str = Field(..., min_length=10)
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(default="", max_length=100)


class InvitationPreviewResponse(BaseModel):
    """Public, non-sensitive preview of an invite (for the accept page)."""

    email: str
    role: TeamRole
    organization_name: str
    expires_at: datetime
    requires_signup: bool = Field(
        ..., description="True if no account exists for this email yet"
    )


class MeResponse(BaseModel):
    """Current user/principal — used by the web dashboard for role gating."""

    user_id: str
    tenant_id: str
    email: str
    name: str
    role: TeamRole
