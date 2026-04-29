"""Bot configuration models."""

import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

# Tones map to additional system-prompt suffixes; keep small and explicit.
BotTone = Literal["professional", "friendly", "concise", "technical", "playful"]
BOT_TONES: tuple[BotTone, ...] = (
    "professional",
    "friendly",
    "concise",
    "technical",
    "playful",
)

# Slug rules — public-readable identifier, no PII or tenant info.
_SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,48}[a-z0-9])?$")


def _validate_slug(value: str) -> str:
    """Validate a slug. Reused by request and stored model."""
    if not _SLUG_PATTERN.match(value):
        raise ValueError(
            "Slug must be 2-50 chars, lowercase a-z, 0-9, or hyphens; "
            "cannot start or end with a hyphen."
        )
    return value


class WidgetConfig(BaseModel):
    """Customizable widget appearance."""

    primary_color: str = Field(
        default="#0f172a",
        pattern=r"^#[0-9a-fA-F]{6}$",
        description="Hex color for the chat bubble and buttons.",
    )
    position: Literal["bottom-right", "bottom-left"] = Field(
        default="bottom-right", description="Anchor position on the host page."
    )
    avatar_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional HTTPS URL to an avatar image.",
    )

    @field_validator("avatar_url")
    @classmethod
    def avatar_must_be_https(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        if not v.startswith("https://"):
            raise ValueError("avatar_url must use https://")
        return v


class ModelConfig(BaseModel):
    """LLM behavior knobs exposed to bot owners."""

    temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    max_tokens: int = Field(default=1024, ge=64, le=8192)


class DocumentFilter(BaseModel):
    """Restricts which documents a bot can search.

    `mode == "all"` lets the bot search the tenant's full corpus.
    `mode == "ids"` restricts to specific document IDs (still tenant-scoped).
    """

    mode: Literal["all", "ids"] = "all"
    document_ids: list[str] = Field(default_factory=list, max_length=200)

    @field_validator("document_ids")
    @classmethod
    def ids_required_for_ids_mode(cls, v: list[str]) -> list[str]:
        # Strip blanks; uniqueness preserved by the caller.
        return [d for d in v if d and d.strip()]


class BotBase(BaseModel):
    """Shared bot fields used in create/update/response."""

    name: str = Field(..., min_length=2, max_length=80)
    slug: str = Field(..., min_length=2, max_length=50)
    description: Optional[str] = Field(default=None, max_length=280)
    system_prompt: str = Field(..., min_length=10, max_length=4000)
    welcome_message: str = Field(
        default="Hi! How can I help you today?", min_length=1, max_length=500
    )
    tone: BotTone = "professional"
    is_public: bool = Field(
        default=False,
        description=(
            "If true, the bot's non-secret config can be fetched without an API "
            "key for embedding. The chat endpoint still requires an API key."
        ),
    )
    model_config_: ModelConfig = Field(default_factory=ModelConfig, alias="model_config")
    widget_config: WidgetConfig = Field(default_factory=WidgetConfig)
    document_filter: DocumentFilter = Field(default_factory=DocumentFilter)

    # Pydantic v2: populate_by_name lets us accept both `model_config`
    # (the API field) and `model_config_` internally without colliding
    # with BaseModel's reserved `model_config` attribute.
    model_config = {"populate_by_name": True}

    @field_validator("slug")
    @classmethod
    def slug_format(cls, v: str) -> str:
        return _validate_slug(v.lower())

    @field_validator("name", "description", "system_prompt", "welcome_message")
    @classmethod
    def strip_strings(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return v.strip()


class CreateBotRequest(BotBase):
    """Body for POST /api/v1/bots."""

    pass


class UpdateBotRequest(BaseModel):
    """Body for PUT /api/v1/bots/{id}. All fields optional."""

    name: Optional[str] = Field(default=None, min_length=2, max_length=80)
    description: Optional[str] = Field(default=None, max_length=280)
    system_prompt: Optional[str] = Field(default=None, min_length=10, max_length=4000)
    welcome_message: Optional[str] = Field(default=None, min_length=1, max_length=500)
    tone: Optional[BotTone] = None
    is_public: Optional[bool] = None
    model_config_: Optional[ModelConfig] = Field(default=None, alias="model_config")
    widget_config: Optional[WidgetConfig] = None
    document_filter: Optional[DocumentFilter] = None

    model_config = {"populate_by_name": True}


class BotResponse(BotBase):
    """Single bot as returned by the API."""

    id: str
    tenant_id: str
    created_at: datetime
    updated_at: datetime


class BotListResponse(BaseModel):
    """List of bots for a tenant."""

    bots: list[BotResponse]


class PublicBotResponse(BaseModel):
    """Public, non-secret subset of a bot for widget embedding.

    Excludes system_prompt, document_filter, and tenant identifiers — none
    of those are needed to render the widget shell, and exposing them would
    leak prompt-engineering and corpus configuration.
    """

    id: str
    slug: str
    name: str
    welcome_message: str
    widget_config: WidgetConfig
