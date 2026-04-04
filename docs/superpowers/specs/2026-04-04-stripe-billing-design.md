# Stripe Billing Integration — Design Spec

**Issue:** #10 — Integrate Stripe for subscription plans and checkout
**Date:** 2026-04-04
**Status:** Approved

## Overview

Implement Stripe-based subscription billing with dynamic model-tier pricing. Users select a plan (Free/Pro/Enterprise) for quotas and a model tier (Starter/Standard/Premium/Ultra) that determines which LLM models are available and the subscription price. The plan tier sets feature limits; the model tier sets the price point.

## Pricing Structure

### Plan Tiers (Quota & Features)

| | Free | Pro | Enterprise |
|--|------|-----|-----------|
| Queries/mo | 50 | 3,000 | 15,000 |
| Documents | 5 | 100 | 500 |
| Bots | 1 | 5 | 20 |
| Model | GPT-5.4 Nano (locked) | User picks tier | User picks tier |

### Model Tiers (Price)

| Model Tier | Cost/query range | Pro Price | Enterprise Price |
|-----------|-----------------|-----------|-----------------|
| Starter | <$0.002 | $19/mo | $49/mo |
| Standard | $0.002–$0.005 | $39/mo | $149/mo |
| Premium | $0.005–$0.015 | $99/mo | $449/mo |
| Ultra | >$0.015 | $149/mo | $749/mo |

### Model Catalog

**Starter tier:**
- Qwen 3.5 Flash (`qwen/qwen3.5-flash-02-23`) — $0.065/$0.26
- GLM-4.7 Flash (`z-ai/glm-4.7-flash`) — $0.06/$0.40
- DeepSeek V3.2 (`deepseek/deepseek-v3.2`) — $0.26/$0.38
- GPT-5.4 Nano (`openai/gpt-5.4-nano`) — $0.20/$1.25
- DeepSeek V3.2 Speciale (`deepseek/deepseek-v3.2-speciale`) — $0.40/$1.20
- Qwen 3.5 397B (`qwen/qwen3.5-397b-a17b`) — $0.39/$2.34

**Standard tier:**
- Haiku 4.5 (`anthropic/claude-haiku-4.5`) — $1.00/$5.00
- GLM-5 Turbo (`z-ai/glm-5-turbo`) — $1.20/$4.00
- MiniMax M2.7 (`minimax/minimax-m2.7`) — $0.30/$1.20

**Premium tier:**
- Gemini 3.1 Pro (`google/gemini-3.1-pro-preview`) — $2.00/$12.00
- Sonnet 4.6 (`anthropic/claude-sonnet-4.6`) — $3.00/$15.00
- GPT-5.3 Codex (`openai/gpt-5.3-codex`) — $1.75/$14.00
- GPT-5.4 (`openai/gpt-5.4`) — $2.50/$15.00

**Ultra tier:**
- Opus 4.6 (`anthropic/claude-opus-4.6`) — $5.00/$25.00

### Margin Analysis (MVP: ~10-20 tenants, M10 MongoDB)

Infrastructure overhead: ~$5-8/tenant/mo (MongoDB M10 $58 + hosting ~$20, split across tenants).

All price points target ~50% gross margin at worst-case model within each tier.

## Data Model

### Enums

```python
class PlanTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"

class ModelTier(str, Enum):
    STARTER = "starter"
    STANDARD = "standard"
    PREMIUM = "premium"
    ULTRA = "ultra"
```

### TenantSettings (modified)

```python
class TenantSettings(BaseModel):
    max_documents: int = 5
    max_chunks: int = 500
    max_queries_per_month: int = 50
    max_bots: int = 1
    model_tier: ModelTier = ModelTier.STARTER
    selected_model: str = "openai/gpt-5.4-nano"
```

### SubscriptionModel (modified)

```python
class SubscriptionModel(BaseModel):
    tenant_id: str
    stripe_customer_id: str
    stripe_subscription_id: Optional[str] = None
    plan: PlanTier = PlanTier.FREE
    model_tier: ModelTier = ModelTier.STARTER
    stripe_price_id: Optional[str] = None
    status: str = "active"  # active, past_due, canceled
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    current_period_queries: int = 0
    created_at: datetime
    updated_at: datetime
```

### Plan Limits Config

```python
PLAN_LIMITS = {
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
```

### Stripe Price Mapping

8 Stripe Prices, one per plan+model_tier combination:

```python
STRIPE_PRICES = {
    ("pro", "starter"): "price_xxx1",      # $19/mo
    ("pro", "standard"): "price_xxx2",     # $39/mo
    ("pro", "premium"): "price_xxx3",      # $99/mo
    ("pro", "ultra"): "price_xxx4",        # $149/mo
    ("enterprise", "starter"): "price_xxx5",   # $49/mo
    ("enterprise", "standard"): "price_xxx6",  # $149/mo
    ("enterprise", "premium"): "price_xxx7",   # $449/mo
    ("enterprise", "ultra"): "price_xxx8",     # $749/mo
}
```

These price IDs are configured via environment variables, not hardcoded.

## API Endpoints

### New Router: `src/routers/billing.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/billing/plans` | Public | Returns plan tiers, model tiers, prices, model catalog |
| `POST` | `/api/v1/billing/checkout` | JWT | Creates Stripe Checkout session, returns URL |
| `POST` | `/api/v1/billing/portal` | JWT | Creates Stripe Customer Portal session, returns URL |
| `GET` | `/api/v1/billing/subscription` | JWT | Returns current subscription, plan, model tier, usage |
| `POST` | `/api/v1/billing/webhook` | Stripe signature | Handles all Stripe webhook events |

### Request/Response Schemas

```python
class CheckoutRequest(BaseModel):
    plan: PlanTier          # "pro" or "enterprise"
    model_tier: ModelTier   # "starter", "standard", "premium", "ultra"
    success_url: str
    cancel_url: str

class CheckoutResponse(BaseModel):
    checkout_url: str

class PortalRequest(BaseModel):
    return_url: str

class PortalResponse(BaseModel):
    portal_url: str

class SubscriptionResponse(BaseModel):
    plan: PlanTier
    model_tier: ModelTier
    status: str
    selected_model: str
    usage: UsageInfo
    limits: LimitsInfo
    current_period_end: Optional[datetime]

class UsageInfo(BaseModel):
    queries_used: int
    queries_limit: int
    documents_used: int
    documents_limit: int

class LimitsInfo(BaseModel):
    queries_per_month: int
    documents: int
    bots: int

class ModelInfo(BaseModel):
    id: str               # OpenRouter model ID
    name: str             # Display name
    provider: str         # Provider name

class ModelTierInfo(BaseModel):
    tier: ModelTier
    pro_price: int        # Monthly price in cents
    enterprise_price: int
    models: list[ModelInfo]

class PlanInfo(BaseModel):
    plan: PlanTier
    limits: LimitsInfo

class PlansResponse(BaseModel):
    plans: list[PlanInfo]
    model_tiers: list[ModelTierInfo]
```

## Service Layer

### `src/services/billing.py` — BillingService

```python
class BillingService:
    async def create_stripe_customer(self, email: str, tenant_id: str) -> str
    async def create_checkout_session(self, tenant_id: str, plan: PlanTier,
                                       model_tier: ModelTier, success_url: str,
                                       cancel_url: str) -> str
    async def create_portal_session(self, tenant_id: str, return_url: str) -> str
    async def get_subscription(self, tenant_id: str) -> SubscriptionModel
    async def handle_checkout_completed(self, session: dict) -> None
    async def handle_invoice_paid(self, invoice: dict) -> None
    async def handle_invoice_failed(self, invoice: dict) -> None
    async def handle_subscription_updated(self, subscription: dict) -> None
    async def handle_subscription_deleted(self, subscription: dict) -> None
```

### Signup Integration

`AuthService.signup()` calls `BillingService.create_stripe_customer()` during tenant creation. A subscription doc is inserted with `plan=free`, `model_tier=starter`, `status=active`.

### Plan Enforcement (FastAPI Dependencies)

```python
async def require_plan_quota(resource: str):
    """Injected into endpoints that consume quota.
    resource: 'queries' | 'documents' | 'bots'
    Returns 403 if at plan limit.
    """

async def get_tenant_model(tenant_id: str) -> str:
    """Returns the selected OpenRouter model ID for the tenant.
    Used by chat endpoint to route LLM calls.
    Free tier always returns 'openai/gpt-5.4-nano' regardless of setting.
    """
```

Injected into:
- `src/routers/chat.py` — `require_plan_quota("queries")` + `get_tenant_model()`
- `src/routers/ingest.py` — `require_plan_quota("documents")`

## Webhook Events & Subscription Lifecycle

### State Machine

```
signup → FREE (stripe_customer_id created, no subscription)
  │
  ├─ checkout.session.completed → ACTIVE (Pro/Enterprise)
  │     │
  │     ├─ invoice.paid → ACTIVE (period extended, query counter reset)
  │     ├─ invoice.payment_failed → PAST_DUE (access maintained, Stripe retries)
  │     │     ├─ invoice.paid → ACTIVE (recovered)
  │     │     └─ customer.subscription.deleted → FREE (failed to recover)
  │     ├─ customer.subscription.updated → ACTIVE (plan/tier change, proration)
  │     └─ customer.subscription.deleted → FREE (user canceled)
  │
  └─ (stays FREE until checkout)
```

### Webhook Handler Details

| Event | Action |
|-------|--------|
| `checkout.session.completed` | Map `price_id` → plan+model_tier. Update tenant plan, limits, model_tier. Upsert subscription doc with status=active. |
| `invoice.paid` | Update `current_period_start/end`. Set status=active. Reset `current_period_queries` to 0. |
| `invoice.payment_failed` | Set status=past_due. No access change (Stripe retries over ~3 weeks). |
| `customer.subscription.updated` | Re-map price_id → plan+model_tier. Update tenant limits. Stripe handles proration billing. |
| `customer.subscription.deleted` | Set plan=free, model_tier=starter. Reset limits to free tier. Clear stripe_subscription_id. |

### Idempotency

Webhook handlers are idempotent via upsert operations. Stripe event IDs are not tracked for MVP — operations are naturally idempotent (setting a value is the same whether done once or twice).

### Query Counting

Increment `current_period_queries` in the subscription doc on each `/chat` call via `$inc`. Reset to 0 on `invoice.paid`. For free users, reset on the 1st of each month via lazy check (compare current date to `current_period_start`).

## Frontend Integration

### Checkout Flow

1. User visits `/dashboard/billing` or `/pricing`
2. Selects Plan (Pro/Enterprise) + Model Tier (dropdown, price updates)
3. Frontend calls `POST /api/v1/billing/checkout`
4. Backend returns Stripe Checkout URL
5. Frontend redirects to Stripe
6. User pays → Stripe redirects to `success_url`
7. Webhook fires → backend updates tenant
8. Dashboard reflects new plan

### Model Selection

Two-level selection:
1. **Model tier** = billing decision (Starter/Standard/Premium/Ultra) — changes subscription price
2. **Specific model** = user preference within tier — stored in `tenant.settings.selected_model`, changeable anytime via API without billing change

### Customer Portal

"Manage Billing" button → `POST /api/v1/billing/portal` → redirect to Stripe Portal for card updates, cancellation, invoice history.

### Frontend Pages (MVP)

| Page | Description |
|------|-------------|
| `/dashboard/billing` | Current plan, usage stats, model selection, upgrade/manage buttons |
| `/pricing` | Public pricing page with plan comparison grid |

No Next.js API routes for billing — everything goes through FastAPI.

## Settings & Configuration

### New Environment Variables

```bash
# apps/api/.env
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PUBLISHABLE_KEY=pk_test_...

# Stripe Price IDs (one per plan+model_tier)
STRIPE_PRICE_PRO_STARTER=price_xxx1
STRIPE_PRICE_PRO_STANDARD=price_xxx2
STRIPE_PRICE_PRO_PREMIUM=price_xxx3
STRIPE_PRICE_PRO_ULTRA=price_xxx4
STRIPE_PRICE_ENTERPRISE_STARTER=price_xxx5
STRIPE_PRICE_ENTERPRISE_STANDARD=price_xxx6
STRIPE_PRICE_ENTERPRISE_PREMIUM=price_xxx7
STRIPE_PRICE_ENTERPRISE_ULTRA=price_xxx8
```

### Stripe Setup (manual, one-time)

1. Create Stripe account in test mode
2. Create 2 Products: "MongoRAG Pro", "MongoRAG Enterprise"
3. Create 4 Prices per Product (starter/standard/premium/ultra amounts)
4. Configure Customer Portal (allow cancel, plan changes)
5. Set up webhook endpoint pointing to `/api/v1/billing/webhook`
6. Subscribe to events: `checkout.session.completed`, `invoice.paid`, `invoice.payment_failed`, `customer.subscription.updated`, `customer.subscription.deleted`

## Testing Strategy

### Unit Tests

| Test | Validates |
|------|-----------|
| `test_plan_limits_config` | All plans have correct quota values |
| `test_stripe_price_mapping` | Every plan+tier combo maps to a price ID |
| `test_model_catalog_tiers` | Every model assigned to exactly one tier |
| `test_webhook_signature_verification` | Rejects invalid signatures, accepts valid |
| `test_checkout_session_creation` | Correct price ID selected for plan+tier |
| `test_plan_enforcement_queries` | Returns 403 when quota exhausted |
| `test_plan_enforcement_documents` | Returns 403 when document limit hit |
| `test_free_tier_model_locked` | Free users always get GPT-5.4 Nano |

### Integration Tests (Stripe test mode)

| Test | Validates |
|------|-----------|
| `test_full_checkout_flow` | Customer → checkout → webhook → tenant upgraded |
| `test_subscription_cancellation` | Webhook → tenant downgraded to free |
| `test_plan_change` | Upgrade/downgrade → correct proration + limits |
| `test_payment_failure` | Failed invoice → status=past_due |
| `test_query_counter_reset` | invoice.paid resets counter to 0 |
| `test_webhook_idempotency` | Same event twice → no double state change |

### Mocking

- Unit tests: mock `stripe` Python SDK
- Integration tests: Stripe test mode + Stripe CLI (`stripe listen --forward-to localhost:8100/api/v1/billing/webhook`)

## File Changes

### New Files

| File | Purpose |
|------|---------|
| `src/routers/billing.py` | Billing API endpoints |
| `src/services/billing.py` | BillingService — Stripe + subscription logic |
| `src/models/billing.py` | ModelTier enum, plan limits, model catalog, price mapping, schemas |
| `tests/unit/test_billing_service.py` | Unit tests |
| `tests/unit/test_plan_limits.py` | Plan config + enforcement tests |
| `tests/unit/test_model_catalog.py` | Model catalog tests |
| `tests/integration/test_checkout_flow.py` | Checkout + webhook integration tests |

### Modified Files

| File | Change |
|------|--------|
| `src/core/settings.py` | Add stripe_secret_key, stripe_webhook_secret, stripe_publishable_key, 8 price ID settings |
| `src/models/tenant.py` | Remove STARTER from PlanTier, add model_tier + selected_model to TenantSettings, add model_tier + stripe_price_id to SubscriptionModel |
| `src/services/auth.py` | Call create_stripe_customer() during signup, insert subscription doc |
| `src/main.py` | Register billing router |
| `src/routers/chat.py` | Inject require_plan_quota("queries"), use get_tenant_model() |
| `src/routers/ingest.py` | Inject require_plan_quota("documents") |
| `pyproject.toml` | Add stripe dependency |

## Out of Scope

- Frontend billing/pricing pages (separate issue)
- Usage-based billing / metered billing (issue #11)
- Rate limiting per minute (issue #11)
- Email notifications for billing events
- Free trial periods
- Annual billing
- Custom enterprise pricing
