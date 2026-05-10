"""Tenant plan tier reader.

Lightweight standalone helper used by routers that need to gate features by
plan without pulling in Stripe-aware ``BillingService`` (which requires a
configured ``STRIPE_SECRET_KEY``).

Reads the same Mongo ``subscriptions`` collection that ``UsageService.get_plan``
and ``BillingService.get_or_create_customer`` use, with identical fallback
semantics: missing record → FREE; non-active status → FREE.
"""

from typing import Iterable

from pymongo.asynchronous.collection import AsyncCollection

from src.models.tenant import PlanTier

# Plans that count as "paid" for feature-gate purposes.
PAID_PLANS: frozenset[PlanTier] = frozenset({PlanTier.STARTER, PlanTier.PRO, PlanTier.ENTERPRISE})

_ACTIVE_STATUSES: frozenset[str] = frozenset({"active", "trialing"})


async def get_tenant_plan(subscriptions_collection: AsyncCollection, tenant_id: str) -> PlanTier:
    """Return the active plan tier for a tenant.

    Falls back to ``PlanTier.FREE`` when:
      * no subscription record exists for the tenant,
      * the record's ``status`` is not active/trialing,
      * the stored ``plan`` value is not a recognized PlanTier.
    """
    sub = await subscriptions_collection.find_one(
        {"tenant_id": tenant_id},
        projection={"plan": 1, "status": 1},
    )
    if not sub:
        return PlanTier.FREE
    if sub.get("status") not in _ACTIVE_STATUSES:
        return PlanTier.FREE
    raw = sub.get("plan")
    if not raw:
        return PlanTier.FREE
    try:
        return PlanTier(raw)
    except ValueError:
        return PlanTier.FREE


def is_paid_plan(plan: PlanTier, paid: Iterable[PlanTier] = PAID_PLANS) -> bool:
    """True if the plan tier is paid (default: STARTER+)."""
    return plan in paid
