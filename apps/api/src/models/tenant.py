"""Tenant and subscription models."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PlanTier(str, Enum):
    """Available subscription plans."""

    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class TenantSettings(BaseModel):
    """Per-tenant configuration."""

    max_documents: int = Field(default=10, description="Max documents allowed")
    max_chunks: int = Field(default=1000, description="Max chunks allowed")
    max_queries_per_day: int = Field(default=100, description="Daily query limit")
    custom_system_prompt: Optional[str] = Field(
        default=None, description="Custom system prompt for the RAG agent"
    )
    allowed_origins: list[str] = Field(
        default_factory=list, description="CORS origins for widget embedding"
    )


class TenantModel(BaseModel):
    """A tenant (customer organization) in the system."""

    tenant_id: str = Field(..., description="Unique tenant identifier")
    name: str = Field(..., description="Organization name")
    slug: str = Field(..., description="URL-safe slug")
    plan: PlanTier = Field(default=PlanTier.FREE, description="Current subscription plan")
    settings: TenantSettings = Field(default_factory=TenantSettings)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SubscriptionModel(BaseModel):
    """Stripe subscription tied to a tenant."""

    tenant_id: str = Field(..., description="Tenant this subscription belongs to")
    stripe_customer_id: str = Field(..., description="Stripe customer ID")
    stripe_subscription_id: Optional[str] = Field(
        default=None, description="Stripe subscription ID"
    )
    plan: PlanTier = Field(default=PlanTier.FREE, description="Current plan")
    status: str = Field(default="active", description="Subscription status")
    current_period_start: Optional[datetime] = Field(default=None)
    current_period_end: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
