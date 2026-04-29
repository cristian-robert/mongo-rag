"""Billing service: Stripe customer/subscription management.

This service is the boundary to the Stripe API. It exposes async methods so
callers can `await` even though `stripe-python` is sync — we offload SDK calls
to a worker thread via `asyncio.to_thread`.

Scope of this issue (#10): customer creation + Checkout Session creation.
Webhook handling lives in issue #43.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import stripe
from pymongo.asynchronous.collection import AsyncCollection

from src.core.settings import Settings
from src.models.billing import (
    NON_CHECKOUT_PLANS,
    ModelTier,
    resolve_stripe_price_id,
)
from src.models.tenant import PlanTier

logger = logging.getLogger(__name__)


class BillingError(Exception):
    """Domain error raised by BillingService for caller-mappable failures."""


class BillingService:
    """Stripe customer + checkout operations scoped per request."""

    def __init__(
        self,
        settings: Settings,
        subscriptions_collection: AsyncCollection,
        tenants_collection: AsyncCollection,
        users_collection: AsyncCollection,
    ) -> None:
        if not settings.stripe_secret_key:
            raise BillingError(
                "Stripe is not configured — set STRIPE_SECRET_KEY in the environment"
            )
        self._settings = settings
        self._subscriptions = subscriptions_collection
        self._tenants = tenants_collection
        self._users = users_collection
        # Capture the API key on the instance instead of mutating module state.
        self._api_key = settings.stripe_secret_key

    # --- Stripe SDK wrappers ---

    async def _stripe_create_customer(
        self, *, email: str, tenant_id: str, idempotency_key: str
    ) -> str:
        """Create a Stripe customer. Returns customer id."""

        def _call() -> stripe.Customer:
            return stripe.Customer.create(
                api_key=self._api_key,
                email=email,
                metadata={"tenant_id": tenant_id},
                idempotency_key=idempotency_key,
            )

        try:
            customer = await asyncio.to_thread(_call)
        except stripe.StripeError as exc:
            logger.exception(
                "stripe_customer_create_failed",
                extra={"tenant_id": tenant_id},
            )
            raise BillingError(f"Stripe customer creation failed: {exc.user_message or exc}")
        return customer.id

    async def _stripe_create_checkout(
        self,
        *,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        tenant_id: str,
        plan: PlanTier,
        model_tier: ModelTier,
        idempotency_key: str,
    ) -> stripe.checkout.Session:
        def _call() -> stripe.checkout.Session:
            return stripe.checkout.Session.create(
                api_key=self._api_key,
                mode="subscription",
                customer=customer_id,
                line_items=[{"price": price_id, "quantity": 1}],
                success_url=success_url,
                cancel_url=cancel_url,
                allow_promotion_codes=True,
                metadata={
                    "tenant_id": tenant_id,
                    "plan": plan.value,
                    "model_tier": model_tier.value,
                },
                subscription_data={
                    "metadata": {
                        "tenant_id": tenant_id,
                        "plan": plan.value,
                        "model_tier": model_tier.value,
                    },
                },
                idempotency_key=idempotency_key,
            )

        try:
            return await asyncio.to_thread(_call)
        except stripe.StripeError as exc:
            logger.exception(
                "stripe_checkout_create_failed",
                extra={"tenant_id": tenant_id, "plan": plan.value, "model_tier": model_tier.value},
            )
            raise BillingError(f"Stripe checkout creation failed: {exc.user_message or exc}")

    # --- Public API ---

    async def get_or_create_customer(self, tenant_id: str) -> str:
        """Return the Stripe customer id for a tenant, creating it if needed.

        Customer ids are persisted on the subscriptions collection. If a
        document already exists with `stripe_customer_id`, that id is reused.
        """
        existing = await self._subscriptions.find_one({"tenant_id": tenant_id})
        if existing and existing.get("stripe_customer_id"):
            return existing["stripe_customer_id"]

        # Find the owning user's email for the Stripe customer record.
        user = await self._users.find_one({"tenant_id": tenant_id, "role": "owner"})
        if not user:
            user = await self._users.find_one({"tenant_id": tenant_id})
        if not user:
            raise BillingError("No user found for tenant")

        # Idempotency keyed on tenant_id ensures retries don't duplicate.
        idempotency_key = f"tenant-customer-{tenant_id}"
        customer_id = await self._stripe_create_customer(
            email=user["email"],
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
        )

        now = datetime.now(timezone.utc)
        await self._subscriptions.update_one(
            {"tenant_id": tenant_id},
            {
                "$set": {
                    "stripe_customer_id": customer_id,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "tenant_id": tenant_id,
                    "plan": PlanTier.FREE.value,
                    "status": "active",
                    "created_at": now,
                },
            },
            upsert=True,
        )

        logger.info(
            "stripe_customer_created",
            extra={"tenant_id": tenant_id, "stripe_customer_id": customer_id},
        )
        return customer_id

    async def create_checkout_session(
        self,
        *,
        tenant_id: str,
        plan: PlanTier,
        model_tier: ModelTier,
        success_url: str,
        cancel_url: str,
    ) -> tuple[str, str]:
        """Create a Stripe Checkout Session for a subscription upgrade.

        Returns (checkout_url, session_id).

        Raises BillingError if the plan/tier combination is not configured
        or if Stripe rejects the request.
        """
        if plan in NON_CHECKOUT_PLANS:
            raise BillingError(f"Plan '{plan.value}' is not purchaseable via Checkout")

        price_id = resolve_stripe_price_id(self._settings, plan, model_tier)
        if not price_id:
            raise BillingError(
                f"No Stripe price configured for plan={plan.value} model_tier={model_tier.value}"
            )

        customer_id = await self.get_or_create_customer(tenant_id)

        # Per-call idempotency token: same tenant rapidly clicking the button
        # should still get distinct sessions because URLs may differ. We
        # combine tenant + price + a uuid4 to make retries safe within a
        # single request boundary. The router supplies a stable suffix when
        # it wants strict idempotency.
        idempotency_key = f"checkout-{tenant_id}-{price_id}-{uuid.uuid4()}"

        session = await self._stripe_create_checkout(
            customer_id=customer_id,
            price_id=price_id,
            success_url=success_url,
            cancel_url=cancel_url,
            tenant_id=tenant_id,
            plan=plan,
            model_tier=model_tier,
            idempotency_key=idempotency_key,
        )

        if not session.url:
            raise BillingError("Stripe returned a checkout session without a URL")

        logger.info(
            "stripe_checkout_session_created",
            extra={
                "tenant_id": tenant_id,
                "session_id": session.id,
                "plan": plan.value,
                "model_tier": model_tier.value,
            },
        )
        return session.url, session.id


def is_safe_redirect_url(url: Optional[str], allowed_hosts: list[str]) -> bool:
    """Best-effort validation of redirect URLs supplied by clients.

    Stripe will reject malformed URLs at the API boundary, but we also
    reject early to avoid being abused as an open redirect proxy. We accept:
      - any https URL whose host is in `allowed_hosts`
      - http URLs only when the host is "localhost" or starts with "127."
    """
    from urllib.parse import urlparse

    if not url:
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    if parsed.scheme == "http":
        return host == "localhost" or host.startswith("127.")
    return host in {h.lower() for h in allowed_hosts}
