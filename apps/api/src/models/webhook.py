"""Webhook configuration and delivery models."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.models.api import StrictRequest

# Event taxonomy. Keep narrow and explicit — every emitted event must be
# present here so the API rejects subscriptions to unknown event types.
WebhookEvent = Literal[
    "document.ingested",
    "document.deleted",
    "chat.completed",
    "subscription.updated",
]
WEBHOOK_EVENTS: tuple[WebhookEvent, ...] = (
    "document.ingested",
    "document.deleted",
    "chat.completed",
    "subscription.updated",
)

MAX_WEBHOOKS_PER_TENANT = 25
MAX_DELIVERY_ATTEMPTS = 5
DELIVERY_TIMEOUT_SECONDS = 30.0


class CreateWebhookRequest(StrictRequest):
    """Body for creating a webhook subscription."""

    url: str = Field(..., min_length=1, max_length=2048)
    events: list[WebhookEvent] = Field(..., min_length=1, max_length=len(WEBHOOK_EVENTS))
    description: Optional[str] = Field(default=None, max_length=200)
    active: bool = Field(default=True)

    @field_validator("events")
    @classmethod
    def _no_duplicate_events(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("events must not contain duplicates")
        return v


class UpdateWebhookRequest(StrictRequest):
    """Body for updating a webhook subscription. All fields optional."""

    url: Optional[str] = Field(default=None, min_length=1, max_length=2048)
    events: Optional[list[WebhookEvent]] = Field(
        default=None, min_length=1, max_length=len(WEBHOOK_EVENTS)
    )
    description: Optional[str] = Field(default=None, max_length=200)
    active: Optional[bool] = None

    @field_validator("events")
    @classmethod
    def _no_duplicate_events(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is not None and len(set(v)) != len(v):
            raise ValueError("events must not contain duplicates")
        return v


class WebhookResponse(BaseModel):
    """A webhook subscription as returned to the dashboard."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    url: str
    events: list[str]
    description: Optional[str] = None
    active: bool
    secret_prefix: str = Field(
        ..., description="First 6 chars of secret — used for UI hint, never the full secret"
    )
    created_at: datetime
    updated_at: datetime


class CreateWebhookResponse(WebhookResponse):
    """First-create response — includes the raw signing secret one time."""

    secret: str = Field(..., description="Raw HMAC signing secret. Shown only at create time.")


class WebhookListResponse(BaseModel):
    webhooks: list[WebhookResponse]


class WebhookDeliveryResponse(BaseModel):
    """A single delivery attempt summary."""

    id: str
    webhook_id: str
    event: str
    status: Literal["pending", "delivered", "failed"]
    attempts: int
    response_code: Optional[int] = None
    last_error: Optional[str] = None
    created_at: datetime
    delivered_at: Optional[datetime] = None


class WebhookDeliveryListResponse(BaseModel):
    deliveries: list[WebhookDeliveryResponse]


class TestFireRequest(StrictRequest):
    """Request body for the test-fire endpoint."""

    event: WebhookEvent = Field(default="document.ingested")
