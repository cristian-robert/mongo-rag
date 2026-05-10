"""Bot configuration models."""

import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# Tones map to additional system-prompt suffixes; keep small and explicit.
BotTone = Literal["professional", "friendly", "concise", "technical", "playful"]
BOT_TONES: tuple[BotTone, ...] = (
    "professional",
    "friendly",
    "concise",
    "technical",
    "playful",
)

# Curated font keys. Single-source-of-truth lives in the widget package
# (`packages/widget/src/fonts.ts`); the conformance test in
# `tests/unit/test_font_conformance.py` asserts that the two stay in sync.
BotFont = Literal[
    "system",
    "inter",
    "geist",
    "ibm-plex-sans",
    "work-sans",
    "fraunces",
    "jetbrains-mono",
]
BOT_FONTS: tuple[BotFont, ...] = (
    "system",
    "inter",
    "geist",
    "ibm-plex-sans",
    "work-sans",
    "fraunces",
    "jetbrains-mono",
)

LauncherIcon = Literal["chat", "sparkle", "book", "question", "custom"]
LauncherShape = Literal["circle", "rounded-square", "pill"]
ColorMode = Literal["light", "dark", "auto"]
RadiusToken = Literal["none", "sm", "md", "lg", "full"]
DensityToken = Literal["compact", "comfortable", "spacious"]
SizeToken = Literal["sm", "md", "lg"]

# Slug rules — public-readable identifier, no PII or tenant info.
_SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,48}[a-z0-9])?$")

# Hex colors: #RRGGBB or #RRGGBBAA (alpha optional). Lowercase or uppercase.
_HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$")

# Maximum URL length for avatar / launcher icon URLs.
_MAX_URL_LENGTH = 500


def _validate_slug(value: str) -> str:
    """Validate a slug. Reused by request and stored model."""
    if not _SLUG_PATTERN.match(value):
        raise ValueError(
            "Slug must be 2-50 chars, lowercase a-z, 0-9, or hyphens; "
            "cannot start or end with a hyphen."
        )
    return value


def _validate_optional_hex(v: Optional[str]) -> Optional[str]:
    """Pydantic validator for optional hex color tokens."""
    if v is None or v == "":
        return None
    if not _HEX_COLOR_PATTERN.match(v):
        raise ValueError("Color must be a hex value like #RRGGBB or #RRGGBBAA")
    return v


def _validate_optional_https(v: Optional[str]) -> Optional[str]:
    """Pydantic validator for optional HTTPS URLs."""
    if v is None or v == "":
        return None
    if len(v) > _MAX_URL_LENGTH:
        raise ValueError(f"URL must be at most {_MAX_URL_LENGTH} characters")
    if not v.startswith("https://"):
        raise ValueError("URL must use https://")
    return v


class WidgetDarkOverrides(BaseModel):
    """Optional dark-mode overrides applied when color_mode is 'dark' or 'auto'.

    Any field left None falls back to an auto-derived dark token (the widget
    rendering layer handles the derivation; the model just transports overrides).
    """

    background: Optional[str] = None
    surface: Optional[str] = None
    foreground: Optional[str] = None
    muted: Optional[str] = None
    border: Optional[str] = None
    primary: Optional[str] = None
    primary_foreground: Optional[str] = None

    @field_validator(
        "background",
        "surface",
        "foreground",
        "muted",
        "border",
        "primary",
        "primary_foreground",
    )
    @classmethod
    def _validate_color(cls, v: Optional[str]) -> Optional[str]:
        return _validate_optional_hex(v)


class WidgetConfig(BaseModel):
    """Customizable widget appearance.

    Field grouping (matches the dashboard form sections):
      * Identity ........ avatar_url, launcher_icon, launcher_icon_url, branding_text
      * Color ........... primary_color, color_mode, background, surface,
                          foreground, muted, border, primary_foreground,
                          dark_overrides
      * Typography ...... font_family, display_font, base_font_size
      * Shape & density . radius, density, launcher_shape, launcher_size,
                          panel_size, position
    """

    # --- Existing fields (kept stable) ---
    primary_color: str = Field(
        default="#0f172a",
        description="Hex color for the chat bubble and buttons.",
    )
    position: Literal["bottom-right", "bottom-left"] = Field(
        default="bottom-right", description="Anchor position on the host page."
    )
    avatar_url: Optional[str] = Field(
        default=None,
        max_length=_MAX_URL_LENGTH,
        description="Optional HTTPS URL to an avatar image.",
    )

    # --- New: color tokens ---
    color_mode: ColorMode = Field(
        default="light",
        description="Active color scheme. 'auto' follows host page preference.",
    )
    background: Optional[str] = Field(
        default=None, description="Main panel background hex (RGB or RGBA)."
    )
    surface: Optional[str] = Field(default=None, description="Inputs / source-card background hex.")
    foreground: Optional[str] = Field(default=None, description="Primary text color hex.")
    muted: Optional[str] = Field(default=None, description="Secondary text color hex.")
    border: Optional[str] = Field(default=None, description="Divider color hex (alpha allowed).")
    primary_foreground: Optional[str] = Field(
        default=None, description="Text color on primary backgrounds."
    )
    dark_overrides: Optional[WidgetDarkOverrides] = Field(
        default=None,
        description=(
            "Per-token dark-mode overrides. Ignored (but accepted) when color_mode is 'light'."
        ),
    )

    # --- New: typography ---
    font_family: BotFont = Field(
        default="system",
        description="Body font from the curated catalog.",
    )
    display_font: Optional[BotFont] = Field(
        default=None,
        description="Optional display font for header/labels. Pairs with font_family.",
    )
    base_font_size: SizeToken = Field(
        default="md", description="Base font size token (sm/md/lg → 13/14/15)."
    )

    # --- New: shape & density ---
    radius: RadiusToken = Field(
        default="md",
        description="Corner radius token. none/sm/md/lg/full → 0/6/14/20/9999.",
    )
    density: DensityToken = Field(default="comfortable", description="Spacing density token.")
    launcher_shape: LauncherShape = Field(default="circle", description="Launcher button shape.")
    launcher_size: SizeToken = Field(
        default="md", description="Launcher diameter token (48/56/64)."
    )
    panel_size: SizeToken = Field(
        default="md",
        description="Panel size token (340x500 / 380x560 / 440x640).",
    )

    # --- New: branding & icons ---
    launcher_icon: LauncherIcon = Field(default="chat", description="Launcher glyph identifier.")
    launcher_icon_url: Optional[str] = Field(
        default=None,
        max_length=_MAX_URL_LENGTH,
        description="HTTPS URL of a custom launcher icon. Required when launcher_icon='custom'.",
    )
    show_avatar_in_messages: bool = Field(
        default=True, description="Render avatar next to assistant messages."
    )
    branding_text: Optional[str] = Field(
        default=None,
        max_length=80,
        description=(
            "Footer branding string. Replaces 'Powered by MongoRAG'. Paid plans only — "
            "the route layer rejects this for free-tier tenants."
        ),
    )

    # --- Validators ---

    @field_validator("primary_color")
    @classmethod
    def primary_color_format(cls, v: str) -> str:
        if not _HEX_COLOR_PATTERN.match(v):
            raise ValueError("primary_color must be a hex value like #RRGGBB or #RRGGBBAA")
        return v

    @field_validator("avatar_url")
    @classmethod
    def avatar_must_be_https(cls, v: Optional[str]) -> Optional[str]:
        return _validate_optional_https(v)

    @field_validator("launcher_icon_url")
    @classmethod
    def launcher_icon_url_must_be_https(cls, v: Optional[str]) -> Optional[str]:
        return _validate_optional_https(v)

    @field_validator(
        "background",
        "surface",
        "foreground",
        "muted",
        "border",
        "primary_foreground",
    )
    @classmethod
    def color_token_format(cls, v: Optional[str]) -> Optional[str]:
        return _validate_optional_hex(v)

    @field_validator("branding_text")
    @classmethod
    def branding_text_strip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @model_validator(mode="after")
    def custom_launcher_requires_url(self) -> "WidgetConfig":
        """When launcher_icon='custom', launcher_icon_url must be set."""
        if self.launcher_icon == "custom" and not self.launcher_icon_url:
            raise ValueError("launcher_icon_url is required when launcher_icon is 'custom'")
        return self


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

    The full WidgetConfig is exposed (it's intentionally cosmetic-only).
    """

    id: str
    slug: str
    name: str
    welcome_message: str
    widget_config: WidgetConfig
