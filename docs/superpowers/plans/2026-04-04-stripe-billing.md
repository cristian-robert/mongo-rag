# Stripe Billing Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Stripe-based subscription billing with dynamic model-tier pricing to the MongoRAG API.

**Architecture:** 8 Stripe Prices (2 plans x 4 model tiers). BillingService handles all Stripe interactions. Webhook endpoint receives Stripe events and updates MongoDB subscription/tenant docs. Plan enforcement via FastAPI dependencies injected into chat and ingest endpoints.

**Tech Stack:** FastAPI, stripe Python SDK, MongoDB (Motor), Pydantic, pytest

**Spec:** `docs/superpowers/specs/2026-04-04-stripe-billing-design.md`

---

## File Map

### New Files

| File | Responsibility |
|------|---------------|
| `src/models/billing.py` | ModelTier enum, plan limits, model catalog, Stripe price mapping, request/response schemas |
| `src/services/billing.py` | BillingService — Stripe customer/checkout/portal/webhook logic |
| `src/routers/billing.py` | Billing API endpoints (plans, checkout, portal, subscription, webhook) |
| `tests/test_billing_models.py` | Unit tests for billing config, plan limits, model catalog |
| `tests/test_billing_service.py` | Unit tests for BillingService (mocked Stripe SDK) |
| `tests/test_billing_router.py` | Unit tests for billing endpoints |

### Modified Files

| File | Change |
|------|--------|
| `pyproject.toml` | Add `stripe` dependency |
| `src/core/settings.py` | Add 11 Stripe env vars (secret key, webhook secret, publishable key, 8 price IDs) |
| `src/models/tenant.py` | Remove STARTER from PlanTier, add `model_tier`/`selected_model` to TenantSettings, add `model_tier`/`stripe_price_id`/`current_period_queries` to SubscriptionModel |
| `src/services/auth.py` | Accept subscriptions_collection, create Stripe customer + subscription doc on signup |
| `src/routers/auth.py` | Pass subscriptions_collection to AuthService |
| `src/core/middleware.py` | Add `/api/v1/billing/webhook` to exempt prefixes |
| `src/main.py` | Register billing router |
| `src/routers/chat.py` | Inject plan quota enforcement dependency |
| `src/routers/ingest.py` | Inject plan quota enforcement dependency |
| `tests/conftest.py` | Add `subscriptions_collection` mock, add Stripe env var defaults |

---

## Task 1: Add stripe dependency and Stripe settings

**Files:**
- Modify: `apps/api/pyproject.toml:6-27`
- Modify: `apps/api/src/core/settings.py:133-153`
- Modify: `apps/api/tests/conftest.py:1-10`

- [ ] **Step 1: Add stripe to pyproject.toml**

In `apps/api/pyproject.toml`, add `"stripe>=11.0.0"` to the `dependencies` list:

```python
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.7.0",
    "pydantic-ai>=0.1.0",
    "pymongo>=4.10.0",
    "openai>=1.58.0",
    "docling>=2.14.0",
    "docling-core>=2.4.0",
    "transformers>=4.47.0",
    "rich>=13.9.0",
    "python-dotenv>=1.0.1",
    "aiofiles>=24.1.0",
    "openai-whisper>=20240930",
    "celery[redis]>=5.4.0",
    "redis>=5.0.0",
    "python-multipart>=0.0.9",
    "bcrypt>=4.2.0",
    "python-jose[cryptography]>=3.3.0",
    "resend>=2.0.0",
    "stripe>=11.0.0",
]
```

- [ ] **Step 2: Add Stripe settings to Settings class**

In `apps/api/src/core/settings.py`, add these fields after the existing `reset_email_from` field (line 152):

```python
    # Stripe Billing
    stripe_secret_key: Optional[str] = Field(
        default=None, description="Stripe secret API key"
    )

    stripe_webhook_secret: Optional[str] = Field(
        default=None, description="Stripe webhook signing secret"
    )

    stripe_publishable_key: Optional[str] = Field(
        default=None, description="Stripe publishable key (returned to frontend)"
    )

    # Stripe Price IDs (one per plan+model_tier combination)
    stripe_price_pro_starter: Optional[str] = Field(default=None)
    stripe_price_pro_standard: Optional[str] = Field(default=None)
    stripe_price_pro_premium: Optional[str] = Field(default=None)
    stripe_price_pro_ultra: Optional[str] = Field(default=None)
    stripe_price_enterprise_starter: Optional[str] = Field(default=None)
    stripe_price_enterprise_standard: Optional[str] = Field(default=None)
    stripe_price_enterprise_premium: Optional[str] = Field(default=None)
    stripe_price_enterprise_ultra: Optional[str] = Field(default=None)
```

Add the `Optional` import if not already present (it is at line 3).

- [ ] **Step 3: Add Stripe env defaults to test conftest**

In `apps/api/tests/conftest.py`, add after the RESEND_API_KEY line (line 7):

```python
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_fake_key_for_tests")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_fake_secret")
os.environ.setdefault("STRIPE_PUBLISHABLE_KEY", "pk_test_fake_key_for_tests")
```

- [ ] **Step 4: Install dependencies**

Run: `cd apps/api && uv sync`
Expected: Success, stripe package installed.

- [ ] **Step 5: Run existing tests to verify no breakage**

Run: `cd apps/api && uv run pytest -x -q`
Expected: All existing tests pass.

- [ ] **Step 6: Commit**

```
git add apps/api/pyproject.toml apps/api/src/core/settings.py apps/api/tests/conftest.py apps/api/uv.lock
git commit -m "chore(api): add stripe dependency and billing settings"
```

---

## Task 2: Update tenant and subscription models

**Files:**
- Modify: `apps/api/src/models/tenant.py`

- [ ] **Step 1: Update PlanTier enum — remove STARTER**

Replace the entire `PlanTier` class:

```python
class PlanTier(str, Enum):
    """Available subscription plans."""

    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"
```

- [ ] **Step 2: Add ModelTier enum**

Add after PlanTier:

```python
class ModelTier(str, Enum):
    """Model quality tiers that determine pricing."""

    STARTER = "starter"
    STANDARD = "standard"
    PREMIUM = "premium"
    ULTRA = "ultra"
```

- [ ] **Step 3: Update TenantSettings**

Replace `TenantSettings` with:

```python
class TenantSettings(BaseModel):
    """Per-tenant configuration."""

    max_documents: int = Field(default=5, description="Max documents allowed")
    max_chunks: int = Field(default=500, description="Max chunks allowed")
    max_queries_per_month: int = Field(default=50, description="Monthly query limit")
    max_bots: int = Field(default=1, description="Max bots allowed")
    model_tier: ModelTier = Field(
        default=ModelTier.STARTER, description="Selected model quality tier"
    )
    selected_model: str = Field(
        default="openai/gpt-5.4-nano",
        description="OpenRouter model ID selected by user within their tier",
    )
    custom_system_prompt: Optional[str] = Field(
        default=None, description="Custom system prompt for the RAG agent"
    )
    allowed_origins: list[str] = Field(
        default_factory=list, description="CORS origins for widget embedding"
    )
```

- [ ] **Step 4: Update SubscriptionModel**

Replace `SubscriptionModel` with:

```python
class SubscriptionModel(BaseModel):
    """Stripe subscription tied to a tenant."""

    tenant_id: str = Field(..., description="Tenant this subscription belongs to")
    stripe_customer_id: str = Field(..., description="Stripe customer ID")
    stripe_subscription_id: Optional[str] = Field(
        default=None, description="Stripe subscription ID"
    )
    plan: PlanTier = Field(default=PlanTier.FREE, description="Current plan")
    model_tier: ModelTier = Field(
        default=ModelTier.STARTER, description="Current model tier"
    )
    stripe_price_id: Optional[str] = Field(
        default=None, description="Active Stripe price ID"
    )
    status: str = Field(default="active", description="Subscription status")
    current_period_start: Optional[datetime] = Field(default=None)
    current_period_end: Optional[datetime] = Field(default=None)
    current_period_queries: int = Field(
        default=0, description="Queries used in current billing period"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 5: Run existing tests**

Run: `cd apps/api && uv run pytest -x -q`
Expected: Some tests may fail due to changed field names (max_queries_per_day → max_queries_per_month). Fix any failures by updating test data to match new field names.

- [ ] **Step 6: Commit**

```
git add apps/api/src/models/tenant.py
git commit -m "refactor(api): update tenant models for billing — add ModelTier, update limits"
```

---

## Task 3: Create billing models, config, and catalog

**Files:**
- Create: `apps/api/src/models/billing.py`
- Create: `apps/api/tests/test_billing_models.py`

- [ ] **Step 1: Write tests for billing config**

Create `apps/api/tests/test_billing_models.py`:

```python
"""Tests for billing models, plan limits, and model catalog."""

import pytest

from src.models.billing import (
    PLAN_LIMITS,
    MODEL_CATALOG,
    CheckoutRequest,
    ModelTier,
    PlansResponse,
    get_price_id,
    get_plan_and_tier_for_price,
)
from src.models.tenant import PlanTier


class TestPlanLimits:
    """Plan limits config is complete and correct."""

    def test_all_plans_have_limits(self):
        for plan in PlanTier:
            assert plan in PLAN_LIMITS, f"Missing limits for {plan}"

    def test_free_limits(self):
        limits = PLAN_LIMITS[PlanTier.FREE]
        assert limits["queries_per_month"] == 50
        assert limits["documents"] == 5
        assert limits["bots"] == 1

    def test_pro_limits(self):
        limits = PLAN_LIMITS[PlanTier.PRO]
        assert limits["queries_per_month"] == 3_000
        assert limits["documents"] == 100
        assert limits["bots"] == 5

    def test_enterprise_limits(self):
        limits = PLAN_LIMITS[PlanTier.ENTERPRISE]
        assert limits["queries_per_month"] == 15_000
        assert limits["documents"] == 500
        assert limits["bots"] == 20

    def test_limits_increase_with_plan_tier(self):
        free = PLAN_LIMITS[PlanTier.FREE]
        pro = PLAN_LIMITS[PlanTier.PRO]
        ent = PLAN_LIMITS[PlanTier.ENTERPRISE]
        assert free["queries_per_month"] < pro["queries_per_month"] < ent["queries_per_month"]
        assert free["documents"] < pro["documents"] < ent["documents"]


class TestModelCatalog:
    """Model catalog is complete and consistent."""

    def test_all_tiers_have_models(self):
        for tier in ModelTier:
            assert tier in MODEL_CATALOG, f"Missing catalog for {tier}"
            assert len(MODEL_CATALOG[tier]) > 0, f"Empty catalog for {tier}"

    def test_each_model_has_required_fields(self):
        for tier, models in MODEL_CATALOG.items():
            for model in models:
                assert "id" in model, f"Missing 'id' in {tier} model"
                assert "name" in model, f"Missing 'name' in {tier} model"
                assert "provider" in model, f"Missing 'provider' in {tier} model"

    def test_free_tier_model_is_in_starter(self):
        starter_ids = [m["id"] for m in MODEL_CATALOG[ModelTier.STARTER]]
        assert "openai/gpt-5.4-nano" in starter_ids


class TestStripePriceMapping:
    """Stripe price ID lookup works for all combinations."""

    def test_get_price_id_returns_setting_value(self):
        """get_price_id uses settings to resolve price IDs."""
        from unittest.mock import MagicMock

        mock_settings = MagicMock()
        mock_settings.stripe_price_pro_starter = "price_pro_starter_123"
        result = get_price_id(PlanTier.PRO, ModelTier.STARTER, mock_settings)
        assert result == "price_pro_starter_123"

    def test_get_price_id_free_returns_none(self):
        from unittest.mock import MagicMock

        mock_settings = MagicMock()
        result = get_price_id(PlanTier.FREE, ModelTier.STARTER, mock_settings)
        assert result is None

    def test_get_plan_and_tier_for_price(self):
        from unittest.mock import MagicMock

        mock_settings = MagicMock()
        mock_settings.stripe_price_pro_starter = "price_abc"
        mock_settings.stripe_price_pro_standard = "price_def"
        mock_settings.stripe_price_pro_premium = None
        mock_settings.stripe_price_pro_ultra = None
        mock_settings.stripe_price_enterprise_starter = None
        mock_settings.stripe_price_enterprise_standard = None
        mock_settings.stripe_price_enterprise_premium = None
        mock_settings.stripe_price_enterprise_ultra = None

        plan, tier = get_plan_and_tier_for_price("price_abc", mock_settings)
        assert plan == PlanTier.PRO
        assert tier == ModelTier.STARTER

    def test_get_plan_and_tier_unknown_price_raises(self):
        from unittest.mock import MagicMock

        mock_settings = MagicMock()
        mock_settings.stripe_price_pro_starter = "price_abc"
        mock_settings.stripe_price_pro_standard = None
        mock_settings.stripe_price_pro_premium = None
        mock_settings.stripe_price_pro_ultra = None
        mock_settings.stripe_price_enterprise_starter = None
        mock_settings.stripe_price_enterprise_standard = None
        mock_settings.stripe_price_enterprise_premium = None
        mock_settings.stripe_price_enterprise_ultra = None

        with pytest.raises(ValueError, match="Unknown Stripe price"):
            get_plan_and_tier_for_price("price_unknown", mock_settings)


class TestCheckoutRequest:
    """CheckoutRequest validation."""

    def test_rejects_free_plan(self):
        with pytest.raises(ValueError):
            CheckoutRequest(
                plan=PlanTier.FREE,
                model_tier=ModelTier.STARTER,
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )

    def test_accepts_pro_plan(self):
        req = CheckoutRequest(
            plan=PlanTier.PRO,
            model_tier=ModelTier.STANDARD,
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )
        assert req.plan == PlanTier.PRO
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && uv run pytest tests/test_billing_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.models.billing'`

- [ ] **Step 3: Create billing models**

Create `apps/api/src/models/billing.py`:

```python
"""Billing configuration: plan limits, model catalog, Stripe price mapping, schemas."""

from typing import Optional

from pydantic import BaseModel, Field, model_validator

from src.models.tenant import ModelTier, PlanTier

# ---------------------------------------------------------------------------
# Plan limits — quota per plan tier
# ---------------------------------------------------------------------------

PLAN_LIMITS: dict[PlanTier, dict[str, int]] = {
    PlanTier.FREE: {
        "queries_per_month": 50,
        "documents": 5,
        "bots": 1,
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

# Default model for free tier (locked — cannot be changed)
FREE_TIER_MODEL = "openai/gpt-5.4-nano"

# ---------------------------------------------------------------------------
# Model catalog — which models belong to which tier
# ---------------------------------------------------------------------------

MODEL_CATALOG: dict[ModelTier, list[dict[str, str]]] = {
    ModelTier.STARTER: [
        {"id": "qwen/qwen3.5-flash-02-23", "name": "Qwen 3.5 Flash", "provider": "Qwen"},
        {"id": "z-ai/glm-4.7-flash", "name": "GLM-4.7 Flash", "provider": "Z.ai"},
        {"id": "deepseek/deepseek-v3.2", "name": "DeepSeek V3.2", "provider": "DeepSeek"},
        {"id": "openai/gpt-5.4-nano", "name": "GPT-5.4 Nano", "provider": "OpenAI"},
        {
            "id": "deepseek/deepseek-v3.2-speciale",
            "name": "DeepSeek V3.2 Speciale",
            "provider": "DeepSeek",
        },
        {"id": "qwen/qwen3.5-397b-a17b", "name": "Qwen 3.5 397B", "provider": "Qwen"},
    ],
    ModelTier.STANDARD: [
        {"id": "anthropic/claude-haiku-4.5", "name": "Haiku 4.5", "provider": "Anthropic"},
        {"id": "z-ai/glm-5-turbo", "name": "GLM-5 Turbo", "provider": "Z.ai"},
        {"id": "minimax/minimax-m2.7", "name": "MiniMax M2.7", "provider": "MiniMax"},
    ],
    ModelTier.PREMIUM: [
        {
            "id": "google/gemini-3.1-pro-preview",
            "name": "Gemini 3.1 Pro",
            "provider": "Google",
        },
        {"id": "anthropic/claude-sonnet-4.6", "name": "Sonnet 4.6", "provider": "Anthropic"},
        {"id": "openai/gpt-5.3-codex", "name": "GPT-5.3 Codex", "provider": "OpenAI"},
        {"id": "openai/gpt-5.4", "name": "GPT-5.4", "provider": "OpenAI"},
    ],
    ModelTier.ULTRA: [
        {"id": "anthropic/claude-opus-4.6", "name": "Opus 4.6", "provider": "Anthropic"},
    ],
}


def get_all_model_ids_for_tier(tier: ModelTier) -> set[str]:
    """Return all valid model IDs for a given tier."""
    return {m["id"] for m in MODEL_CATALOG[tier]}


# ---------------------------------------------------------------------------
# Stripe price mapping — resolves (plan, model_tier) → Stripe price ID
# ---------------------------------------------------------------------------

_PRICE_SETTING_MAP: dict[tuple[str, str], str] = {
    ("pro", "starter"): "stripe_price_pro_starter",
    ("pro", "standard"): "stripe_price_pro_standard",
    ("pro", "premium"): "stripe_price_pro_premium",
    ("pro", "ultra"): "stripe_price_pro_ultra",
    ("enterprise", "starter"): "stripe_price_enterprise_starter",
    ("enterprise", "standard"): "stripe_price_enterprise_standard",
    ("enterprise", "premium"): "stripe_price_enterprise_premium",
    ("enterprise", "ultra"): "stripe_price_enterprise_ultra",
}


def get_price_id(plan: PlanTier, model_tier: ModelTier, settings) -> Optional[str]:
    """Look up the Stripe price ID for a plan+model_tier combo.

    Returns None for the free plan (no Stripe subscription).
    """
    if plan == PlanTier.FREE:
        return None
    attr = _PRICE_SETTING_MAP.get((plan.value, model_tier.value))
    if not attr:
        return None
    return getattr(settings, attr, None)


def get_plan_and_tier_for_price(
    price_id: str, settings
) -> tuple[PlanTier, ModelTier]:
    """Reverse-map a Stripe price ID to (PlanTier, ModelTier).

    Raises ValueError if price_id is not found in settings.
    """
    for (plan_val, tier_val), attr in _PRICE_SETTING_MAP.items():
        if getattr(settings, attr, None) == price_id:
            return PlanTier(plan_val), ModelTier(tier_val)
    raise ValueError(f"Unknown Stripe price ID: {price_id}")


# ---------------------------------------------------------------------------
# Request/Response schemas
# ---------------------------------------------------------------------------


class CheckoutRequest(BaseModel):
    """Request to create a Stripe Checkout session."""

    plan: PlanTier
    model_tier: ModelTier
    success_url: str
    cancel_url: str

    @model_validator(mode="after")
    def plan_must_be_paid(self):
        if self.plan == PlanTier.FREE:
            raise ValueError("Cannot checkout for the free plan")
        return self


class CheckoutResponse(BaseModel):
    checkout_url: str


class PortalRequest(BaseModel):
    return_url: str


class PortalResponse(BaseModel):
    portal_url: str


class UsageInfo(BaseModel):
    queries_used: int
    queries_limit: int
    documents_used: int
    documents_limit: int


class LimitsInfo(BaseModel):
    queries_per_month: int
    documents: int
    bots: int


class SubscriptionResponse(BaseModel):
    plan: PlanTier
    model_tier: ModelTier
    status: str
    selected_model: str
    usage: UsageInfo
    limits: LimitsInfo
    current_period_end: Optional[str] = None


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str


class ModelTierInfo(BaseModel):
    tier: ModelTier
    pro_price_cents: int
    enterprise_price_cents: int
    models: list[ModelInfo]


class PlanInfo(BaseModel):
    plan: PlanTier
    limits: LimitsInfo


class PlansResponse(BaseModel):
    plans: list[PlanInfo]
    model_tiers: list[ModelTierInfo]


class SelectModelRequest(BaseModel):
    """Request to change the selected model within the current tier."""

    model_id: str
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/api && uv run pytest tests/test_billing_models.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```
git add apps/api/src/models/billing.py apps/api/tests/test_billing_models.py
git commit -m "feat(api): add billing models — plan limits, model catalog, price mapping"
```

---

## Task 4: Create BillingService

**Files:**
- Create: `apps/api/src/services/billing.py`
- Create: `apps/api/tests/test_billing_service.py`

- [ ] **Step 1: Write tests for BillingService**

Create `apps/api/tests/test_billing_service.py`:

```python
"""Tests for BillingService."""

import os

os.environ.setdefault("NEXTAUTH_SECRET", "test-secret-for-unit-tests-minimum-32chars")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_fake")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_fake")

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.billing import PLAN_LIMITS, ModelTier
from src.models.tenant import PlanTier
from src.services.billing import BillingService


@pytest.fixture
def mock_subscriptions():
    coll = MagicMock()
    coll.find_one = AsyncMock()
    coll.update_one = AsyncMock()
    coll.insert_one = AsyncMock()
    return coll


@pytest.fixture
def mock_tenants():
    coll = MagicMock()
    coll.update_one = AsyncMock()
    return coll


@pytest.fixture
def mock_documents():
    coll = MagicMock()
    coll.count_documents = AsyncMock(return_value=3)
    return coll


@pytest.fixture
def mock_settings():
    s = MagicMock()
    s.stripe_secret_key = "sk_test_fake"
    s.stripe_webhook_secret = "whsec_test_fake"
    s.stripe_price_pro_starter = "price_pro_starter"
    s.stripe_price_pro_standard = "price_pro_standard"
    s.stripe_price_pro_premium = "price_pro_premium"
    s.stripe_price_pro_ultra = "price_pro_ultra"
    s.stripe_price_enterprise_starter = "price_ent_starter"
    s.stripe_price_enterprise_standard = "price_ent_standard"
    s.stripe_price_enterprise_premium = "price_ent_premium"
    s.stripe_price_enterprise_ultra = "price_ent_ultra"
    return s


@pytest.fixture
def service(mock_subscriptions, mock_tenants, mock_documents, mock_settings):
    return BillingService(
        subscriptions_collection=mock_subscriptions,
        tenants_collection=mock_tenants,
        documents_collection=mock_documents,
        settings=mock_settings,
    )


class TestCreateStripeCustomer:
    @patch("src.services.billing.stripe")
    async def test_creates_customer_and_returns_id(self, mock_stripe, service):
        mock_stripe.Customer.create = MagicMock(
            return_value=MagicMock(id="cus_test123")
        )
        result = await service.create_stripe_customer("user@example.com", "tenant-1")
        assert result == "cus_test123"
        mock_stripe.Customer.create.assert_called_once_with(
            email="user@example.com",
            metadata={"tenant_id": "tenant-1"},
        )


class TestCreateCheckoutSession:
    @patch("src.services.billing.stripe")
    async def test_creates_session_and_returns_url(
        self, mock_stripe, service, mock_subscriptions
    ):
        mock_subscriptions.find_one = AsyncMock(
            return_value={"stripe_customer_id": "cus_123", "tenant_id": "t1"}
        )
        mock_stripe.checkout.Session.create = MagicMock(
            return_value=MagicMock(url="https://checkout.stripe.com/session_abc")
        )
        url = await service.create_checkout_session(
            tenant_id="t1",
            plan=PlanTier.PRO,
            model_tier=ModelTier.STARTER,
            success_url="https://app.com/success",
            cancel_url="https://app.com/cancel",
        )
        assert url == "https://checkout.stripe.com/session_abc"

    async def test_raises_if_no_subscription(self, service, mock_subscriptions):
        mock_subscriptions.find_one = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="No subscription found"):
            await service.create_checkout_session(
                tenant_id="t1",
                plan=PlanTier.PRO,
                model_tier=ModelTier.STARTER,
                success_url="https://app.com/s",
                cancel_url="https://app.com/c",
            )


class TestHandleCheckoutCompleted:
    async def test_activates_subscription(self, service, mock_subscriptions, mock_tenants):
        session = {
            "subscription": "sub_123",
            "metadata": {"tenant_id": "t1"},
        }
        # Mock the Stripe subscription fetch
        with patch("src.services.billing.stripe") as mock_stripe:
            mock_stripe.Subscription.retrieve = MagicMock(
                return_value=MagicMock(
                    id="sub_123",
                    items=MagicMock(data=[MagicMock(price=MagicMock(id="price_pro_starter"))]),
                    current_period_start=1700000000,
                    current_period_end=1702592000,
                )
            )
            await service.handle_checkout_completed(session)

        mock_subscriptions.update_one.assert_called_once()
        call_args = mock_subscriptions.update_one.call_args
        update_doc = call_args[0][1]["$set"]
        assert update_doc["plan"] == "pro"
        assert update_doc["model_tier"] == "starter"
        assert update_doc["status"] == "active"
        assert update_doc["stripe_subscription_id"] == "sub_123"

        mock_tenants.update_one.assert_called_once()


class TestHandleSubscriptionDeleted:
    async def test_downgrades_to_free(self, service, mock_subscriptions, mock_tenants):
        subscription = {"metadata": {"tenant_id": "t1"}}
        await service.handle_subscription_deleted(subscription)

        sub_update = mock_subscriptions.update_one.call_args[0][1]["$set"]
        assert sub_update["plan"] == "free"
        assert sub_update["model_tier"] == "starter"
        assert sub_update["status"] == "canceled"
        assert sub_update["stripe_subscription_id"] is None

        tenant_update = mock_tenants.update_one.call_args[0][1]["$set"]
        assert tenant_update["plan"] == "free"
        assert tenant_update["settings.max_queries_per_month"] == 50


class TestHandleInvoicePaid:
    async def test_resets_query_counter(self, service, mock_subscriptions):
        invoice = {
            "subscription": "sub_123",
            "lines": {"data": [{"price": {"id": "price_pro_starter"}}]},
            "period_start": 1700000000,
            "period_end": 1702592000,
        }
        with patch("src.services.billing.stripe") as mock_stripe:
            mock_stripe.Subscription.retrieve = MagicMock(
                return_value=MagicMock(metadata={"tenant_id": "t1"})
            )
            await service.handle_invoice_paid(invoice)

        update = mock_subscriptions.update_one.call_args[0][1]["$set"]
        assert update["current_period_queries"] == 0
        assert update["status"] == "active"


class TestHandleInvoiceFailed:
    async def test_marks_past_due(self, service, mock_subscriptions):
        invoice = {"subscription": "sub_123"}
        with patch("src.services.billing.stripe") as mock_stripe:
            mock_stripe.Subscription.retrieve = MagicMock(
                return_value=MagicMock(metadata={"tenant_id": "t1"})
            )
            await service.handle_invoice_failed(invoice)

        update = mock_subscriptions.update_one.call_args[0][1]["$set"]
        assert update["status"] == "past_due"


class TestGetSubscription:
    async def test_returns_subscription(self, service, mock_subscriptions, mock_documents):
        mock_subscriptions.find_one = AsyncMock(
            return_value={
                "tenant_id": "t1",
                "plan": "pro",
                "model_tier": "starter",
                "status": "active",
                "current_period_queries": 42,
                "current_period_end": datetime(2026, 5, 1, tzinfo=timezone.utc),
            }
        )
        result = await service.get_subscription("t1")
        assert result["plan"] == "pro"
        assert result["usage"]["queries_used"] == 42
        assert result["usage"]["queries_limit"] == 3_000
        assert result["usage"]["documents_used"] == 3

    async def test_returns_none_if_not_found(self, service, mock_subscriptions):
        mock_subscriptions.find_one = AsyncMock(return_value=None)
        result = await service.get_subscription("t1")
        assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && uv run pytest tests/test_billing_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.services.billing'`

- [ ] **Step 3: Create BillingService**

Create `apps/api/src/services/billing.py`:

```python
"""Billing service: Stripe customer, checkout, portal, webhook handling."""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import stripe
from pymongo.asynchronous.collection import AsyncCollection

from src.models.billing import (
    FREE_TIER_MODEL,
    PLAN_LIMITS,
    get_plan_and_tier_for_price,
    get_price_id,
)
from src.models.tenant import ModelTier, PlanTier

logger = logging.getLogger(__name__)


class BillingService:
    """Handles Stripe billing operations and subscription state."""

    def __init__(
        self,
        subscriptions_collection: AsyncCollection,
        tenants_collection: AsyncCollection,
        documents_collection: AsyncCollection,
        settings: Any,
    ) -> None:
        self._subscriptions = subscriptions_collection
        self._tenants = tenants_collection
        self._documents = documents_collection
        self._settings = settings
        stripe.api_key = settings.stripe_secret_key

    async def create_stripe_customer(self, email: str, tenant_id: str) -> str:
        """Create a Stripe customer and return the customer ID."""
        customer = stripe.Customer.create(
            email=email,
            metadata={"tenant_id": tenant_id},
        )
        return customer.id

    async def create_checkout_session(
        self,
        tenant_id: str,
        plan: PlanTier,
        model_tier: ModelTier,
        success_url: str,
        cancel_url: str,
    ) -> str:
        """Create a Stripe Checkout session and return the URL."""
        sub = await self._subscriptions.find_one({"tenant_id": tenant_id})
        if not sub:
            raise ValueError(f"No subscription found for tenant {tenant_id}")

        price_id = get_price_id(plan, model_tier, self._settings)
        if not price_id:
            raise ValueError(f"No Stripe price configured for {plan}/{model_tier}")

        session = stripe.checkout.Session.create(
            customer=sub["stripe_customer_id"],
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"tenant_id": tenant_id},
            subscription_data={"metadata": {"tenant_id": tenant_id}},
        )
        return session.url

    async def create_portal_session(self, tenant_id: str, return_url: str) -> str:
        """Create a Stripe Customer Portal session and return the URL."""
        sub = await self._subscriptions.find_one({"tenant_id": tenant_id})
        if not sub:
            raise ValueError(f"No subscription found for tenant {tenant_id}")

        session = stripe.billing_portal.Session.create(
            customer=sub["stripe_customer_id"],
            return_url=return_url,
        )
        return session.url

    async def get_subscription(self, tenant_id: str) -> Optional[dict]:
        """Return subscription info with usage stats, or None."""
        sub = await self._subscriptions.find_one({"tenant_id": tenant_id})
        if not sub:
            return None

        plan = PlanTier(sub.get("plan", "free"))
        limits = PLAN_LIMITS[plan]
        doc_count = await self._documents.count_documents({"tenant_id": tenant_id})

        period_end = sub.get("current_period_end")

        return {
            "plan": sub.get("plan", "free"),
            "model_tier": sub.get("model_tier", "starter"),
            "status": sub.get("status", "active"),
            "selected_model": sub.get("selected_model", FREE_TIER_MODEL),
            "usage": {
                "queries_used": sub.get("current_period_queries", 0),
                "queries_limit": limits["queries_per_month"],
                "documents_used": doc_count,
                "documents_limit": limits["documents"],
            },
            "limits": limits,
            "current_period_end": period_end.isoformat() if period_end else None,
        }

    # -- Webhook handlers (idempotent) --

    async def handle_checkout_completed(self, session: dict) -> None:
        """Activate subscription after successful checkout."""
        tenant_id = session["metadata"]["tenant_id"]
        stripe_sub_id = session["subscription"]

        # Fetch the subscription to get the price ID
        stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
        price_id = stripe_sub.items.data[0].price.id
        plan, model_tier = get_plan_and_tier_for_price(price_id, self._settings)
        limits = PLAN_LIMITS[plan]

        now = datetime.now(timezone.utc)
        await self._subscriptions.update_one(
            {"tenant_id": tenant_id},
            {
                "$set": {
                    "stripe_subscription_id": stripe_sub_id,
                    "stripe_price_id": price_id,
                    "plan": plan.value,
                    "model_tier": model_tier.value,
                    "status": "active",
                    "current_period_start": datetime.fromtimestamp(
                        stripe_sub.current_period_start, tz=timezone.utc
                    ),
                    "current_period_end": datetime.fromtimestamp(
                        stripe_sub.current_period_end, tz=timezone.utc
                    ),
                    "current_period_queries": 0,
                    "updated_at": now,
                }
            },
            upsert=True,
        )

        await self._tenants.update_one(
            {"tenant_id": tenant_id},
            {
                "$set": {
                    "plan": plan.value,
                    "settings.model_tier": model_tier.value,
                    "settings.max_queries_per_month": limits["queries_per_month"],
                    "settings.max_documents": limits["documents"],
                    "settings.max_bots": limits["bots"],
                    "updated_at": now,
                }
            },
        )

        logger.info(
            "subscription_activated",
            extra={"tenant_id": tenant_id, "plan": plan.value, "model_tier": model_tier.value},
        )

    async def handle_invoice_paid(self, invoice: dict) -> None:
        """Extend subscription period and reset query counter."""
        stripe_sub_id = invoice["subscription"]
        stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
        tenant_id = stripe_sub.metadata["tenant_id"]

        now = datetime.now(timezone.utc)
        await self._subscriptions.update_one(
            {"tenant_id": tenant_id},
            {
                "$set": {
                    "status": "active",
                    "current_period_start": datetime.fromtimestamp(
                        invoice["period_start"], tz=timezone.utc
                    ),
                    "current_period_end": datetime.fromtimestamp(
                        invoice["period_end"], tz=timezone.utc
                    ),
                    "current_period_queries": 0,
                    "updated_at": now,
                }
            },
        )

        logger.info("invoice_paid", extra={"tenant_id": tenant_id})

    async def handle_invoice_failed(self, invoice: dict) -> None:
        """Mark subscription as past_due."""
        stripe_sub_id = invoice["subscription"]
        stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
        tenant_id = stripe_sub.metadata["tenant_id"]

        now = datetime.now(timezone.utc)
        await self._subscriptions.update_one(
            {"tenant_id": tenant_id},
            {"$set": {"status": "past_due", "updated_at": now}},
        )

        logger.info("invoice_payment_failed", extra={"tenant_id": tenant_id})

    async def handle_subscription_updated(self, subscription: dict) -> None:
        """Handle plan or model tier change."""
        tenant_id = subscription["metadata"]["tenant_id"]
        price_id = subscription["items"]["data"][0]["price"]["id"]

        plan, model_tier = get_plan_and_tier_for_price(price_id, self._settings)
        limits = PLAN_LIMITS[plan]

        now = datetime.now(timezone.utc)
        await self._subscriptions.update_one(
            {"tenant_id": tenant_id},
            {
                "$set": {
                    "plan": plan.value,
                    "model_tier": model_tier.value,
                    "stripe_price_id": price_id,
                    "updated_at": now,
                }
            },
        )

        await self._tenants.update_one(
            {"tenant_id": tenant_id},
            {
                "$set": {
                    "plan": plan.value,
                    "settings.model_tier": model_tier.value,
                    "settings.max_queries_per_month": limits["queries_per_month"],
                    "settings.max_documents": limits["documents"],
                    "settings.max_bots": limits["bots"],
                    "updated_at": now,
                }
            },
        )

        logger.info(
            "subscription_updated",
            extra={"tenant_id": tenant_id, "plan": plan.value, "model_tier": model_tier.value},
        )

    async def handle_subscription_deleted(self, subscription: dict) -> None:
        """Downgrade tenant to free plan."""
        tenant_id = subscription["metadata"]["tenant_id"]
        free_limits = PLAN_LIMITS[PlanTier.FREE]

        now = datetime.now(timezone.utc)
        await self._subscriptions.update_one(
            {"tenant_id": tenant_id},
            {
                "$set": {
                    "plan": PlanTier.FREE.value,
                    "model_tier": ModelTier.STARTER.value,
                    "status": "canceled",
                    "stripe_subscription_id": None,
                    "stripe_price_id": None,
                    "updated_at": now,
                }
            },
        )

        await self._tenants.update_one(
            {"tenant_id": tenant_id},
            {
                "$set": {
                    "plan": PlanTier.FREE.value,
                    "settings.model_tier": ModelTier.STARTER.value,
                    "settings.selected_model": FREE_TIER_MODEL,
                    "settings.max_queries_per_month": free_limits["queries_per_month"],
                    "settings.max_documents": free_limits["documents"],
                    "settings.max_bots": free_limits["bots"],
                    "updated_at": now,
                }
            },
        )

        logger.info("subscription_deleted", extra={"tenant_id": tenant_id})

    async def increment_query_count(self, tenant_id: str) -> None:
        """Increment the query counter for the current billing period."""
        await self._subscriptions.update_one(
            {"tenant_id": tenant_id},
            {"$inc": {"current_period_queries": 1}},
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/api && uv run pytest tests/test_billing_service.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```
git add apps/api/src/services/billing.py apps/api/tests/test_billing_service.py
git commit -m "feat(api): add BillingService — Stripe checkout, portal, webhook handlers"
```

---

## Task 5: Create billing router

**Files:**
- Create: `apps/api/src/routers/billing.py`
- Create: `apps/api/tests/test_billing_router.py`
- Modify: `apps/api/src/main.py`
- Modify: `apps/api/src/core/middleware.py`

- [ ] **Step 1: Write tests for billing router**

Create `apps/api/tests/test_billing_router.py`:

```python
"""Tests for billing router endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import MOCK_TENANT_ID, make_auth_header


@pytest.fixture
def mock_billing_service():
    service = MagicMock()
    service.create_checkout_session = AsyncMock(
        return_value="https://checkout.stripe.com/test"
    )
    service.create_portal_session = AsyncMock(
        return_value="https://billing.stripe.com/portal"
    )
    service.get_subscription = AsyncMock(
        return_value={
            "plan": "pro",
            "model_tier": "starter",
            "status": "active",
            "selected_model": "openai/gpt-5.4-nano",
            "usage": {
                "queries_used": 10,
                "queries_limit": 3000,
                "documents_used": 2,
                "documents_limit": 100,
            },
            "limits": {"queries_per_month": 3000, "documents": 100, "bots": 5},
            "current_period_end": "2026-05-01T00:00:00+00:00",
        }
    )
    return service


class TestGetPlans:
    def test_returns_plans_and_model_tiers(self, client):
        resp = client.get("/api/v1/billing/plans")
        assert resp.status_code == 200
        data = resp.json()
        assert "plans" in data
        assert "model_tiers" in data
        assert len(data["plans"]) == 3  # free, pro, enterprise
        assert len(data["model_tiers"]) == 4  # starter, standard, premium, ultra


class TestCheckout:
    def test_creates_checkout_session(self, client, mock_billing_service):
        with patch(
            "src.routers.billing._get_billing_service",
            return_value=mock_billing_service,
        ):
            resp = client.post(
                "/api/v1/billing/checkout",
                json={
                    "plan": "pro",
                    "model_tier": "starter",
                    "success_url": "https://app.com/success",
                    "cancel_url": "https://app.com/cancel",
                },
                headers=make_auth_header(),
            )
        assert resp.status_code == 200
        assert resp.json()["checkout_url"] == "https://checkout.stripe.com/test"

    def test_rejects_free_plan(self, client):
        resp = client.post(
            "/api/v1/billing/checkout",
            json={
                "plan": "free",
                "model_tier": "starter",
                "success_url": "https://app.com/success",
                "cancel_url": "https://app.com/cancel",
            },
            headers=make_auth_header(),
        )
        assert resp.status_code == 422

    def test_requires_auth(self, client):
        resp = client.post(
            "/api/v1/billing/checkout",
            json={
                "plan": "pro",
                "model_tier": "starter",
                "success_url": "https://app.com/success",
                "cancel_url": "https://app.com/cancel",
            },
        )
        assert resp.status_code == 401


class TestGetSubscription:
    def test_returns_subscription(self, client, mock_billing_service):
        with patch(
            "src.routers.billing._get_billing_service",
            return_value=mock_billing_service,
        ):
            resp = client.get(
                "/api/v1/billing/subscription",
                headers=make_auth_header(),
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"] == "pro"
        assert data["usage"]["queries_used"] == 10


class TestPortal:
    def test_creates_portal_session(self, client, mock_billing_service):
        with patch(
            "src.routers.billing._get_billing_service",
            return_value=mock_billing_service,
        ):
            resp = client.post(
                "/api/v1/billing/portal",
                json={"return_url": "https://app.com/dashboard"},
                headers=make_auth_header(),
            )
        assert resp.status_code == 200
        assert resp.json()["portal_url"] == "https://billing.stripe.com/portal"


class TestWebhook:
    def test_rejects_invalid_signature(self, client):
        resp = client.post(
            "/api/v1/billing/webhook",
            content=b"{}",
            headers={"stripe-signature": "invalid"},
        )
        assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && uv run pytest tests/test_billing_router.py -v`
Expected: FAIL — import errors.

- [ ] **Step 3: Create billing router**

Create `apps/api/src/routers/billing.py`:

```python
"""Billing endpoints: plans, checkout, portal, subscription, webhook."""

import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request

from src.core.dependencies import AgentDependencies
from src.core.deps import get_deps
from src.core.tenant import get_tenant_id_from_jwt
from src.models.billing import (
    MODEL_CATALOG,
    PLAN_LIMITS,
    CheckoutRequest,
    CheckoutResponse,
    LimitsInfo,
    ModelInfo,
    ModelTierInfo,
    PlanInfo,
    PlansResponse,
    PortalRequest,
    PortalResponse,
    SubscriptionResponse,
)
from src.models.tenant import ModelTier, PlanTier
from src.services.billing import BillingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])

# Monthly prices in cents for display purposes
_PRICES_CENTS: dict[tuple[str, str], tuple[int, int]] = {
    # (model_tier): (pro_price_cents, enterprise_price_cents)
    ("starter",): (1900, 4900),
    ("standard",): (3900, 14900),
    ("premium",): (9900, 44900),
    ("ultra",): (14900, 74900),
}


def _get_billing_service(deps: AgentDependencies = Depends(get_deps)) -> BillingService:
    return BillingService(
        subscriptions_collection=deps.subscriptions_collection,
        tenants_collection=deps.tenants_collection,
        documents_collection=deps.documents_collection,
        settings=deps.settings,
    )


@router.get("/plans", response_model=PlansResponse)
async def get_plans():
    """Return available plans, model tiers, and model catalog."""
    plans = [
        PlanInfo(
            plan=plan,
            limits=LimitsInfo(
                queries_per_month=limits["queries_per_month"],
                documents=limits["documents"],
                bots=limits["bots"],
            ),
        )
        for plan, limits in PLAN_LIMITS.items()
    ]

    tier_prices = {
        ModelTier.STARTER: (1900, 4900),
        ModelTier.STANDARD: (3900, 14900),
        ModelTier.PREMIUM: (9900, 44900),
        ModelTier.ULTRA: (14900, 74900),
    }

    model_tiers = [
        ModelTierInfo(
            tier=tier,
            pro_price_cents=prices[0],
            enterprise_price_cents=prices[1],
            models=[ModelInfo(**m) for m in MODEL_CATALOG[tier]],
        )
        for tier, prices in tier_prices.items()
    ]

    return PlansResponse(plans=plans, model_tiers=model_tiers)


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    body: CheckoutRequest,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    service: BillingService = Depends(_get_billing_service),
):
    """Create a Stripe Checkout session for upgrading."""
    try:
        url = await service.create_checkout_session(
            tenant_id=tenant_id,
            plan=body.plan,
            model_tier=body.model_tier,
            success_url=body.success_url,
            cancel_url=body.cancel_url,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return CheckoutResponse(checkout_url=url)


@router.post("/portal", response_model=PortalResponse)
async def create_portal(
    body: PortalRequest,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    service: BillingService = Depends(_get_billing_service),
):
    """Create a Stripe Customer Portal session."""
    try:
        url = await service.create_portal_session(
            tenant_id=tenant_id,
            return_url=body.return_url,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return PortalResponse(portal_url=url)


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    service: BillingService = Depends(_get_billing_service),
):
    """Return current subscription status and usage."""
    result = await service.get_subscription(tenant_id)
    if not result:
        raise HTTPException(status_code=404, detail="No subscription found")

    return result


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    deps: AgentDependencies = Depends(get_deps),
):
    """Handle Stripe webhook events."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            deps.settings.stripe_webhook_secret,
        )
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    service = BillingService(
        subscriptions_collection=deps.subscriptions_collection,
        tenants_collection=deps.tenants_collection,
        documents_collection=deps.documents_collection,
        settings=deps.settings,
    )

    event_type = event["type"]
    data = event["data"]["object"]

    try:
        if event_type == "checkout.session.completed":
            await service.handle_checkout_completed(data)
        elif event_type == "invoice.paid":
            await service.handle_invoice_paid(data)
        elif event_type == "invoice.payment_failed":
            await service.handle_invoice_failed(data)
        elif event_type == "customer.subscription.updated":
            await service.handle_subscription_updated(data)
        elif event_type == "customer.subscription.deleted":
            await service.handle_subscription_deleted(data)
        else:
            logger.info("unhandled_stripe_event", extra={"type": event_type})
    except Exception:
        logger.exception("webhook_handler_error", extra={"type": event_type})
        # Return 200 anyway — Stripe retries on non-2xx, and we don't want
        # retries for bugs (we'd just fail again). Log and investigate.

    return {"received": True}
```

- [ ] **Step 4: Add webhook route to middleware exempt list**

In `apps/api/src/core/middleware.py`, update `_EXEMPT_PREFIXES`:

```python
_EXEMPT_PREFIXES = (
    "/api/v1/auth",
    "/api/v1/billing/webhook",
    "/api/v1/billing/plans",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
)
```

- [ ] **Step 5: Register billing router in main.py**

In `apps/api/src/main.py`, add the import and include:

```python
from src.routers.billing import router as billing_router
```

And at the end of the router registrations:

```python
app.include_router(billing_router)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd apps/api && uv run pytest tests/test_billing_router.py -v`
Expected: All tests PASS.

- [ ] **Step 7: Commit**

```
git add apps/api/src/routers/billing.py apps/api/tests/test_billing_router.py apps/api/src/main.py apps/api/src/core/middleware.py
git commit -m "feat(api): add billing router — checkout, portal, subscription, webhook endpoints"
```

---

## Task 6: Integrate Stripe customer creation into signup

**Files:**
- Modify: `apps/api/src/services/auth.py`
- Modify: `apps/api/src/routers/auth.py`
- Modify: `apps/api/tests/conftest.py`

- [ ] **Step 1: Write test for signup creating Stripe customer**

Add to `apps/api/tests/test_billing_service.py`:

```python
class TestSignupIntegration:
    """AuthService.signup creates Stripe customer + subscription doc."""

    @patch("src.services.billing.stripe")
    async def test_signup_creates_stripe_customer(self, mock_stripe):
        mock_stripe.Customer.create = MagicMock(
            return_value=MagicMock(id="cus_new_tenant")
        )

        mock_users = MagicMock()
        mock_users.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id="user_id_1")
        )
        mock_users.find_one = AsyncMock(return_value=None)

        mock_tenants = MagicMock()
        mock_tenants.insert_one = AsyncMock()

        mock_subs = MagicMock()
        mock_subs.insert_one = AsyncMock()

        mock_reset = MagicMock()

        mock_settings = MagicMock()
        mock_settings.stripe_secret_key = "sk_test"

        from src.services.auth import AuthService

        service = AuthService(
            users_collection=mock_users,
            tenants_collection=mock_tenants,
            reset_tokens_collection=mock_reset,
            subscriptions_collection=mock_subs,
            settings=mock_settings,
        )

        result = await service.signup("new@example.com", "password123", "New Org")

        # Stripe customer was created
        mock_stripe.Customer.create.assert_called_once()
        call_kwargs = mock_stripe.Customer.create.call_args[1]
        assert call_kwargs["email"] == "new@example.com"

        # Subscription doc was inserted
        mock_subs.insert_one.assert_called_once()
        sub_doc = mock_subs.insert_one.call_args[0][0]
        assert sub_doc["stripe_customer_id"] == "cus_new_tenant"
        assert sub_doc["plan"] == "free"
        assert sub_doc["tenant_id"] == result["tenant_id"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_billing_service.py::TestSignupIntegration -v`
Expected: FAIL — AuthService doesn't accept subscriptions_collection yet.

- [ ] **Step 3: Update AuthService to create Stripe customer on signup**

In `apps/api/src/services/auth.py`, update `__init__` and `signup`:

```python
class AuthService:
    """Handles user signup, login, and password reset."""

    def __init__(
        self,
        users_collection: AsyncCollection,
        tenants_collection: AsyncCollection,
        reset_tokens_collection: AsyncCollection,
        subscriptions_collection: AsyncCollection = None,
        settings: Any = None,
    ) -> None:
        self._users = users_collection
        self._tenants = tenants_collection
        self._reset_tokens = reset_tokens_collection
        self._subscriptions = subscriptions_collection
        self._settings = settings
```

Add `from typing import Any` to imports if needed (it's already there).

In the `signup` method, after the tenant insert and before the user insert, add Stripe customer creation:

```python
        # Create Stripe customer and subscription doc
        stripe_customer_id = None
        if self._subscriptions is not None and self._settings is not None:
            from src.services.billing import BillingService

            billing = BillingService(
                subscriptions_collection=self._subscriptions,
                tenants_collection=self._tenants,
                documents_collection=None,  # Not needed for customer creation
                settings=self._settings,
            )
            stripe_customer_id = await billing.create_stripe_customer(email, tenant_id)

            sub_doc = {
                "tenant_id": tenant_id,
                "stripe_customer_id": stripe_customer_id,
                "stripe_subscription_id": None,
                "plan": "free",
                "model_tier": "starter",
                "status": "active",
                "current_period_queries": 0,
                "current_period_start": None,
                "current_period_end": None,
                "created_at": now,
                "updated_at": now,
            }
            await self._subscriptions.insert_one(sub_doc)
```

- [ ] **Step 4: Update auth router to pass new dependencies**

In `apps/api/src/routers/auth.py`, update `_get_auth_service`:

```python
def _get_auth_service(deps: AgentDependencies = Depends(get_deps)) -> AuthService:
    """Create AuthService with injected collections."""
    return AuthService(
        users_collection=deps.users_collection,
        tenants_collection=deps.tenants_collection,
        reset_tokens_collection=deps.reset_tokens_collection,
        subscriptions_collection=deps.subscriptions_collection,
        settings=deps.settings,
    )
```

- [ ] **Step 5: Update conftest to add subscriptions_collection mock**

In `apps/api/tests/conftest.py`, add to `mock_deps` fixture:

```python
    deps.subscriptions_collection = MagicMock()
```

(This line may already exist — verify and add only if missing.)

- [ ] **Step 6: Run all tests**

Run: `cd apps/api && uv run pytest -x -q`
Expected: All tests PASS. Some existing auth tests may need the new `subscriptions_collection` parameter — fix any failures.

- [ ] **Step 7: Commit**

```
git add apps/api/src/services/auth.py apps/api/src/routers/auth.py apps/api/tests/conftest.py apps/api/tests/test_billing_service.py
git commit -m "feat(api): create Stripe customer and subscription doc on signup"
```

---

## Task 7: Add plan enforcement dependencies

**Files:**
- Create: `apps/api/src/core/plan_enforcement.py`
- Modify: `apps/api/src/routers/chat.py`
- Modify: `apps/api/src/routers/ingest.py`

- [ ] **Step 1: Write tests for plan enforcement**

Add to `apps/api/tests/test_billing_service.py`:

```python
class TestPlanEnforcement:
    """Plan quota enforcement dependencies."""

    async def test_query_quota_allows_when_under_limit(self):
        from src.core.plan_enforcement import check_query_quota

        mock_subs = MagicMock()
        mock_subs.find_one = AsyncMock(
            return_value={
                "plan": "pro",
                "current_period_queries": 100,
                "status": "active",
            }
        )
        # Should not raise
        await check_query_quota("tenant-1", mock_subs)

    async def test_query_quota_blocks_when_at_limit(self):
        from src.core.plan_enforcement import check_query_quota

        mock_subs = MagicMock()
        mock_subs.find_one = AsyncMock(
            return_value={
                "plan": "free",
                "current_period_queries": 50,
                "status": "active",
            }
        )
        with pytest.raises(HTTPException) as exc_info:
            await check_query_quota("tenant-1", mock_subs)
        assert exc_info.value.status_code == 403

    async def test_document_quota_blocks_when_at_limit(self):
        from src.core.plan_enforcement import check_document_quota

        mock_subs = MagicMock()
        mock_subs.find_one = AsyncMock(
            return_value={"plan": "free", "status": "active"}
        )
        mock_docs = MagicMock()
        mock_docs.count_documents = AsyncMock(return_value=5)

        with pytest.raises(HTTPException) as exc_info:
            await check_document_quota("tenant-1", mock_subs, mock_docs)
        assert exc_info.value.status_code == 403

    async def test_get_tenant_model_returns_selected(self):
        from src.core.plan_enforcement import get_tenant_model

        mock_tenants = MagicMock()
        mock_tenants.find_one = AsyncMock(
            return_value={
                "plan": "pro",
                "settings": {"selected_model": "anthropic/claude-haiku-4.5"},
            }
        )
        model = await get_tenant_model("tenant-1", mock_tenants)
        assert model == "anthropic/claude-haiku-4.5"

    async def test_get_tenant_model_free_returns_locked(self):
        from src.core.plan_enforcement import get_tenant_model

        mock_tenants = MagicMock()
        mock_tenants.find_one = AsyncMock(
            return_value={
                "plan": "free",
                "settings": {"selected_model": "anthropic/claude-haiku-4.5"},
            }
        )
        model = await get_tenant_model("tenant-1", mock_tenants)
        assert model == "openai/gpt-5.4-nano"
```

Add this import at the top of the test file:

```python
from fastapi import HTTPException
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && uv run pytest tests/test_billing_service.py::TestPlanEnforcement -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.core.plan_enforcement'`

- [ ] **Step 3: Create plan enforcement module**

Create `apps/api/src/core/plan_enforcement.py`:

```python
"""Plan enforcement — quota checks as reusable async functions."""

import logging

from fastapi import HTTPException
from pymongo.asynchronous.collection import AsyncCollection

from src.models.billing import FREE_TIER_MODEL, PLAN_LIMITS
from src.models.tenant import PlanTier

logger = logging.getLogger(__name__)


async def check_query_quota(
    tenant_id: str,
    subscriptions_collection: AsyncCollection,
) -> None:
    """Raise 403 if tenant has exhausted their monthly query quota."""
    sub = await subscriptions_collection.find_one({"tenant_id": tenant_id})
    if not sub:
        raise HTTPException(status_code=403, detail="No subscription found")

    plan = PlanTier(sub.get("plan", "free"))
    limit = PLAN_LIMITS[plan]["queries_per_month"]
    used = sub.get("current_period_queries", 0)

    if used >= limit:
        raise HTTPException(
            status_code=403,
            detail=f"Monthly query limit reached ({limit}). Upgrade your plan for more.",
        )


async def check_document_quota(
    tenant_id: str,
    subscriptions_collection: AsyncCollection,
    documents_collection: AsyncCollection,
) -> None:
    """Raise 403 if tenant has reached their document limit."""
    sub = await subscriptions_collection.find_one({"tenant_id": tenant_id})
    if not sub:
        raise HTTPException(status_code=403, detail="No subscription found")

    plan = PlanTier(sub.get("plan", "free"))
    limit = PLAN_LIMITS[plan]["documents"]
    count = await documents_collection.count_documents({"tenant_id": tenant_id})

    if count >= limit:
        raise HTTPException(
            status_code=403,
            detail=f"Document limit reached ({limit}). Upgrade your plan for more.",
        )


async def get_tenant_model(
    tenant_id: str,
    tenants_collection: AsyncCollection,
) -> str:
    """Return the OpenRouter model ID for this tenant.

    Free tier always returns the locked free model regardless of settings.
    """
    tenant = await tenants_collection.find_one({"tenant_id": tenant_id})
    if not tenant:
        return FREE_TIER_MODEL

    plan = tenant.get("plan", "free")
    if plan == PlanTier.FREE.value:
        return FREE_TIER_MODEL

    settings = tenant.get("settings", {})
    return settings.get("selected_model", FREE_TIER_MODEL)
```

- [ ] **Step 4: Run enforcement tests**

Run: `cd apps/api && uv run pytest tests/test_billing_service.py::TestPlanEnforcement -v`
Expected: All PASS.

- [ ] **Step 5: Inject quota check into chat endpoint**

In `apps/api/src/routers/chat.py`, add imports:

```python
from src.core.plan_enforcement import check_query_quota
from src.services.billing import BillingService
```

In the `chat_endpoint` function, add after `tenant_id` is resolved (before creating ChatService):

```python
    # Enforce query quota
    await check_query_quota(tenant_id, deps.subscriptions_collection)
```

And after a successful response (before the return), add query counter increment:

```python
    # Increment query counter
    await deps.subscriptions_collection.update_one(
        {"tenant_id": tenant_id},
        {"$inc": {"current_period_queries": 1}},
    )
```

- [ ] **Step 6: Inject quota check into ingest endpoint**

In `apps/api/src/routers/ingest.py`, add import:

```python
from src.core.plan_enforcement import check_document_quota
```

In `ingest_document_endpoint`, add after `tenant_id` is resolved:

```python
    # Enforce document quota
    await check_document_quota(tenant_id, deps.subscriptions_collection, deps.documents_collection)
```

- [ ] **Step 7: Run all tests**

Run: `cd apps/api && uv run pytest -x -q`
Expected: All tests PASS.

- [ ] **Step 8: Commit**

```
git add apps/api/src/core/plan_enforcement.py apps/api/src/routers/chat.py apps/api/src/routers/ingest.py apps/api/tests/test_billing_service.py
git commit -m "feat(api): add plan enforcement — query and document quota checks"
```

---

## Task 8: Fix existing tests and run full suite

**Files:**
- Modify: various test files as needed

- [ ] **Step 1: Run full test suite and fix any failures**

Run: `cd apps/api && uv run pytest -v`

Fix any failures caused by:
- Changed field names (`max_queries_per_day` → `max_queries_per_month`)
- Removed `STARTER` from `PlanTier`
- New required mock collections (`subscriptions_collection`)
- New imports in modified files

- [ ] **Step 2: Run linting**

Run: `cd apps/api && uv run ruff check .`
Run: `cd apps/api && uv run ruff format --check .`

Fix any lint/format issues.

- [ ] **Step 3: Commit fixes**

```
git add -A
git commit -m "fix(api): update tests and fix lint for billing integration"
```

---

## Task 9: Update seed data and documentation

**Files:**
- Modify: `apps/api/scripts/seed_data.py`

- [ ] **Step 1: Update seed data to include subscription doc with new fields**

In `apps/api/scripts/seed_data.py`, update `SEED_SUBSCRIPTION` to include new fields:

```python
SEED_SUBSCRIPTION = {
    "tenant_id": SEED_TENANT_ID,
    "stripe_customer_id": "cus_seed_test",
    "stripe_subscription_id": None,
    "plan": "free",
    "model_tier": "starter",
    "stripe_price_id": None,
    "status": "active",
    "current_period_start": None,
    "current_period_end": None,
    "current_period_queries": 0,
    "created_at": _NOW,
    "updated_at": _NOW,
}
```

Also update `SEED_TENANT` settings if needed to match new field names.

- [ ] **Step 2: Run seed script to verify**

Run: `cd apps/api && uv run python -m scripts.seed_data` (or equivalent)
Expected: No errors.

- [ ] **Step 3: Commit**

```
git add apps/api/scripts/seed_data.py
git commit -m "chore(api): update seed data with billing fields"
```

---

## Task 10: Final verification

- [ ] **Step 1: Run full test suite**

Run: `cd apps/api && uv run pytest -v --tb=short`
Expected: All tests PASS.

- [ ] **Step 2: Run lint and format**

Run: `cd apps/api && uv run ruff check . && uv run ruff format --check .`
Expected: No issues.

- [ ] **Step 3: Verify dev server starts**

Run: `cd apps/api && uv run uvicorn src.main:app --port 8100`
Expected: Server starts without errors. Check http://localhost:8100/docs to verify billing endpoints appear.

- [ ] **Step 4: Test /api/v1/billing/plans endpoint**

Run: `curl http://localhost:8100/api/v1/billing/plans | python -m json.tool`
Expected: Returns plans and model tiers JSON.

- [ ] **Step 5: Final commit if any cleanup needed**

```
git add -A
git commit -m "chore(api): final cleanup for billing integration"
```
