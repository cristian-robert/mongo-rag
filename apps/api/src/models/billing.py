"""Billing models, plan configuration, and model catalog.

This module is the single source of truth for:
- Plan tiers and their quotas (PLAN_LIMITS)
- Model tiers and the model catalog (MODEL_CATALOG)
- Stripe price ID resolution (resolve_stripe_price_id)
- Request/response schemas for billing endpoints

Aligned with `docs/superpowers/specs/2026-04-04-stripe-billing-design.md`.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from src.models.tenant import PlanTier


class ModelTier(str, Enum):
    """Model price tier — drives subscription price within a plan."""

    STARTER = "starter"
    STANDARD = "standard"
    PREMIUM = "premium"
    ULTRA = "ultra"


# Plan-level quota limits.
# PRO/ENTERPRISE values come from the design spec; FREE/STARTER kept aligned with
# the existing tenants schema so legacy free-tier accounts retain their quota.
PLAN_LIMITS: dict[PlanTier, dict[str, int]] = {
    PlanTier.FREE: {
        "queries_per_month": 50,
        "documents": 5,
        "bots": 1,
    },
    PlanTier.STARTER: {
        "queries_per_month": 500,
        "documents": 25,
        "bots": 2,
    },
    PlanTier.PRO: {
        "queries_per_month": 3_000,
        "documents": 100,
        "bots": 5,
    },
    PlanTier.ENTERPRISE: {
        "queries_per_month": 15_000,
        "documents": 500,
        "bots": 20,
    },
}

# Model catalog grouped by tier. Each entry: (model_id, display_name, provider).
MODEL_CATALOG: dict[ModelTier, list[tuple[str, str, str]]] = {
    ModelTier.STARTER: [
        ("openai/gpt-5.4-nano", "GPT-5.4 Nano", "OpenAI"),
        ("qwen/qwen3.5-flash-02-23", "Qwen 3.5 Flash", "Qwen"),
        ("z-ai/glm-4.7-flash", "GLM-4.7 Flash", "Z-AI"),
        ("deepseek/deepseek-v3.2", "DeepSeek V3.2", "DeepSeek"),
    ],
    ModelTier.STANDARD: [
        ("anthropic/claude-haiku-4.5", "Claude Haiku 4.5", "Anthropic"),
        ("z-ai/glm-5-turbo", "GLM-5 Turbo", "Z-AI"),
        ("minimax/minimax-m2.7", "MiniMax M2.7", "MiniMax"),
    ],
    ModelTier.PREMIUM: [
        ("anthropic/claude-sonnet-4.6", "Claude Sonnet 4.6", "Anthropic"),
        ("google/gemini-3.1-pro-preview", "Gemini 3.1 Pro", "Google"),
        ("openai/gpt-5.4", "GPT-5.4", "OpenAI"),
    ],
    ModelTier.ULTRA: [
        ("anthropic/claude-opus-4.6", "Claude Opus 4.6", "Anthropic"),
    ],
}

# Default model exposed to the free tier (not user-selectable).
FREE_TIER_MODEL = "openai/gpt-5.4-nano"


# --- Pydantic schemas ---


class CheckoutRequest(BaseModel):
    """Request body for POST /api/v1/billing/checkout."""

    plan: PlanTier = Field(..., description="Target plan: pro or enterprise")
    model_tier: ModelTier = Field(..., description="Model tier inside the plan")
    success_url: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="URL Stripe redirects to after successful checkout",
    )
    cancel_url: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="URL Stripe redirects to if checkout is cancelled",
    )


class CheckoutResponse(BaseModel):
    """Response from POST /api/v1/billing/checkout."""

    checkout_url: str = Field(..., description="Stripe-hosted checkout session URL")
    session_id: str = Field(..., description="Stripe checkout session id")


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str


class ModelTierInfo(BaseModel):
    tier: ModelTier
    pro_price_cents: Optional[int] = Field(
        default=None, description="Monthly price (cents) for Pro plan at this tier"
    )
    enterprise_price_cents: Optional[int] = Field(
        default=None, description="Monthly price (cents) for Enterprise plan at this tier"
    )
    models: list[ModelInfo]


class LimitsInfo(BaseModel):
    queries_per_month: int
    documents: int
    bots: int


class PlanInfo(BaseModel):
    plan: PlanTier
    limits: LimitsInfo


class PlansResponse(BaseModel):
    plans: list[PlanInfo]
    model_tiers: list[ModelTierInfo]


# Display prices in cents — used by /plans for the public pricing page.
# Source-of-truth prices live in Stripe; these are display-only.
DISPLAY_PRICES_CENTS: dict[tuple[PlanTier, ModelTier], int] = {
    (PlanTier.PRO, ModelTier.STARTER): 1_900,
    (PlanTier.PRO, ModelTier.STANDARD): 3_900,
    (PlanTier.PRO, ModelTier.PREMIUM): 9_900,
    (PlanTier.PRO, ModelTier.ULTRA): 14_900,
    (PlanTier.ENTERPRISE, ModelTier.STARTER): 4_900,
    (PlanTier.ENTERPRISE, ModelTier.STANDARD): 14_900,
    (PlanTier.ENTERPRISE, ModelTier.PREMIUM): 44_900,
    (PlanTier.ENTERPRISE, ModelTier.ULTRA): 74_900,
}


# Plans that are not purchaseable via Stripe Checkout.
NON_CHECKOUT_PLANS: frozenset[PlanTier] = frozenset({PlanTier.FREE, PlanTier.STARTER})


def resolve_stripe_price_id(settings, plan: PlanTier, model_tier: ModelTier) -> Optional[str]:
    """Look up the configured Stripe price ID for a (plan, model_tier) combo.

    Returns None if the combination isn't configured (e.g. missing env var).
    Free/Starter plans cannot be purchased via Checkout — caller should
    short-circuit those before calling this.
    """
    attr = f"stripe_price_{plan.value}_{model_tier.value}"
    return getattr(settings, attr, None)
