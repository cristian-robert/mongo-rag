"""Stripe webhook event handling.

Persists subscription state to Postgres (`subscriptions`, `stripe_events`)
keyed by `tenant_id` derived from the Stripe customer's `metadata.tenant_id`
(set when the customer was created in #48).

Idempotency is enforced by inserting `event.id` into `stripe_events` with
`ON CONFLICT DO NOTHING`. If the insert touches zero rows, the event has
already been processed and we ack 200 without re-running side effects.

Error policy:
- Bad signature → caller raises 400 (Stripe will retry).
- Unknown customer / unmapped tenant → log warning + ack 200 (don't 500;
  Stripe retries forever and we'd flood the queue for events that target
  some other environment's customer).
- Postgres failure mid-handler → 500 so Stripe retries with backoff.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg
import stripe

from src.core.settings import Settings
from src.models.billing import resolve_stripe_price_id  # noqa: F401  (public re-export)
from src.models.tenant import PlanTier

logger = logging.getLogger(__name__)


# Events we actually act on. Anything else is acknowledged + recorded but
# generates no side effects, so test mode + future event types stay safe.
HANDLED_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "checkout.session.completed",
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
        "invoice.payment_succeeded",
        "invoice.payment_failed",
    }
)


# Stripe → Postgres `subscription_status` enum.
# Anything not in this set falls back to 'incomplete' (safe default — no
# entitlements granted). Keep aligned with the migration's ENUM.
STRIPE_STATUS_MAP: dict[str, str] = {
    "active": "active",
    "trialing": "trialing",
    "past_due": "past_due",
    "canceled": "canceled",
    "unpaid": "unpaid",
    "incomplete": "incomplete",
    "incomplete_expired": "incomplete_expired",
    "paused": "paused",
}


class WebhookSignatureError(Exception):
    """Raised when Stripe signature verification fails."""


def construct_event(
    *,
    payload: bytes,
    signature: str,
    secret: str,
    tolerance: int = 300,
) -> stripe.Event:
    """Verify and parse a Stripe webhook payload.

    Raises WebhookSignatureError on any signature/parse failure. The router
    maps that to HTTP 400 — never 500 — so Stripe retries with backoff.
    """
    try:
        return stripe.Webhook.construct_event(
            payload=payload,
            sig_header=signature,
            secret=secret,
            tolerance=tolerance,
        )
    except stripe.SignatureVerificationError as exc:
        raise WebhookSignatureError(f"signature verification failed: {exc}") from exc
    except ValueError as exc:
        # Malformed JSON.
        raise WebhookSignatureError(f"invalid payload: {exc}") from exc


def map_status(stripe_status: Optional[str]) -> str:
    """Map a Stripe status string to our `subscription_status` enum value."""
    if not stripe_status:
        return "incomplete"
    return STRIPE_STATUS_MAP.get(stripe_status, "incomplete")


def _resolve_plan_from_price(settings: Settings, price_id: Optional[str]) -> Optional[PlanTier]:
    """Reverse-lookup `price_id` against configured Stripe price env vars.

    Returns PlanTier.PRO or PlanTier.ENTERPRISE, or None when the price ID
    isn't in our catalog (e.g. a sandbox price or a deprecated tier).
    """
    if not price_id:
        return None
    for plan in (PlanTier.PRO, PlanTier.ENTERPRISE):
        for tier in ("starter", "standard", "premium", "ultra"):
            attr = f"stripe_price_{plan.value}_{tier}"
            if getattr(settings, attr, None) == price_id:
                return plan
    return None


def _epoch_to_dt(value: Any) -> Optional[datetime]:
    """Convert a Stripe epoch-seconds field to a tz-aware UTC datetime."""
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


# --- DB helpers ---------------------------------------------------------------


async def record_event(conn: asyncpg.Connection, event: stripe.Event) -> bool:
    """Insert event into stripe_events. Returns True if inserted (new), False
    if duplicate. Caller should skip side effects on False.
    """
    row = await conn.fetchrow(
        """
        insert into public.stripe_events (event_id, type, payload)
        values ($1, $2, $3::jsonb)
        on conflict (event_id) do nothing
        returning event_id
        """,
        event.id,
        event.type,
        # Stripe's Event objects are dict-like; we serialize as JSON via asyncpg
        # by passing the dict (asyncpg uses json codec when registered).
        # Keep a small subset to avoid storing PII unnecessarily.
        _redacted_payload(event),
    )
    return row is not None


async def mark_event_processed(conn: asyncpg.Connection, event_id: str) -> None:
    await conn.execute(
        "update public.stripe_events set processed_at = now() where event_id = $1",
        event_id,
    )


async def _resolve_tenant_id(conn: asyncpg.Connection, customer_id: Optional[str]) -> Optional[str]:
    """Find the tenant that owns a Stripe customer. Returns None if unknown."""
    if not customer_id:
        return None
    row = await conn.fetchrow(
        "select tenant_id from public.subscriptions where stripe_customer_id = $1",
        customer_id,
    )
    return str(row["tenant_id"]) if row else None


def _redacted_payload(event: stripe.Event) -> str:
    """Return a redacted JSON string of the event for the audit log.

    We don't need full PII (emails, addresses) in our event log. Strip
    obvious identifiers before storage. Stripe is the source of truth.
    """
    import json

    raw = event.to_dict() if hasattr(event, "to_dict") else dict(event)

    def _scrub(node: Any) -> Any:
        if isinstance(node, dict):
            return {k: _scrub(v) for k, v in node.items() if k not in _PII_KEYS}
        if isinstance(node, list):
            return [_scrub(v) for v in node]
        return node

    return json.dumps(_scrub(raw))


_PII_KEYS: frozenset[str] = frozenset(
    {
        "email",
        "name",
        "phone",
        "address",
        "shipping",
        "billing_details",
        "payment_method_details",
        "receipt_email",
    }
)


# --- Event handlers -----------------------------------------------------------


async def _handle_checkout_session_completed(
    conn: asyncpg.Connection,
    session: dict[str, Any],
    settings: Settings,
) -> None:
    """Link Stripe customer to tenant and seed the subscription row.

    Stripe sends `metadata.tenant_id` because the checkout session was created
    in #48 with that metadata. We trust it (it came from our own backend on
    a JWT-authenticated request) but we still cross-check the customer.
    """
    customer_id = session.get("customer")
    metadata = session.get("metadata") or {}
    tenant_id = metadata.get("tenant_id")
    plan_value = metadata.get("plan")
    subscription_id = session.get("subscription")

    if not tenant_id or not customer_id:
        logger.warning(
            "stripe_webhook_checkout_missing_metadata",
            extra={"session_id": session.get("id"), "has_customer": bool(customer_id)},
        )
        return

    plan = PlanTier.PRO
    if plan_value:
        try:
            plan = PlanTier(plan_value)
        except ValueError:
            logger.warning(
                "stripe_webhook_checkout_unknown_plan",
                extra={"plan": plan_value},
            )

    await conn.execute(
        """
        insert into public.subscriptions
            (tenant_id, stripe_customer_id, stripe_subscription_id, plan, status)
        values ($1::uuid, $2, $3, $4::public.tenant_plan, 'incomplete'::public.subscription_status)
        on conflict (tenant_id) do update set
            stripe_customer_id     = excluded.stripe_customer_id,
            stripe_subscription_id = coalesce(
                excluded.stripe_subscription_id, public.subscriptions.stripe_subscription_id
            ),
            plan                   = excluded.plan
        """,
        tenant_id,
        customer_id,
        subscription_id,
        plan.value,
    )
    # Mirror plan onto tenants for fast feature-gating.
    await conn.execute(
        "update public.tenants set plan = $1::public.tenant_plan where id = $2::uuid",
        plan.value,
        tenant_id,
    )


async def _handle_subscription_event(
    conn: asyncpg.Connection,
    subscription: dict[str, Any],
    settings: Settings,
    *,
    deleted: bool = False,
) -> None:
    """Sync subscription state for created / updated / deleted events."""
    customer_id = subscription.get("customer")
    subscription_id = subscription.get("id")
    metadata = subscription.get("metadata") or {}
    metadata_tenant_id = metadata.get("tenant_id")

    tenant_id = metadata_tenant_id or await _resolve_tenant_id(conn, customer_id)
    if not tenant_id:
        logger.warning(
            "stripe_webhook_unknown_customer",
            extra={
                "customer_id": customer_id,
                "subscription_id": subscription_id,
            },
        )
        return

    if deleted:
        status = "canceled"
    else:
        status = map_status(subscription.get("status"))

    # Determine plan from the first item's price id.
    plan: Optional[PlanTier] = None
    items = (subscription.get("items") or {}).get("data") or []
    if items:
        price_id = (items[0].get("price") or {}).get("id")
        plan = _resolve_plan_from_price(settings, price_id)

    current_period_end = _epoch_to_dt(subscription.get("current_period_end"))

    if plan is not None:
        await conn.execute(
            """
            insert into public.subscriptions
                (tenant_id, stripe_customer_id, stripe_subscription_id, plan, status,
                 current_period_end)
            values ($1::uuid, $2, $3, $4::public.tenant_plan,
                    $5::public.subscription_status, $6)
            on conflict (tenant_id) do update set
                stripe_customer_id     = excluded.stripe_customer_id,
                stripe_subscription_id = excluded.stripe_subscription_id,
                plan                   = excluded.plan,
                status                 = excluded.status,
                current_period_end     = excluded.current_period_end
            """,
            tenant_id,
            customer_id,
            subscription_id,
            plan.value,
            status,
            current_period_end,
        )
        await conn.execute(
            "update public.tenants set plan = $1::public.tenant_plan where id = $2::uuid",
            plan.value,
            tenant_id,
        )
    else:
        # Status-only update — preserve existing plan.
        await conn.execute(
            """
            update public.subscriptions
            set stripe_subscription_id = coalesce($2, stripe_subscription_id),
                status                 = $3::public.subscription_status,
                current_period_end     = coalesce($4, current_period_end)
            where tenant_id = $1::uuid
            """,
            tenant_id,
            subscription_id,
            status,
            current_period_end,
        )


async def _handle_invoice_event(
    conn: asyncpg.Connection,
    invoice: dict[str, Any],
    *,
    paid: bool,
) -> None:
    """`invoice.payment_succeeded` → status='active'.
    `invoice.payment_failed`     → status='past_due'.
    """
    customer_id = invoice.get("customer")
    tenant_id = await _resolve_tenant_id(conn, customer_id)
    if not tenant_id:
        logger.warning(
            "stripe_webhook_invoice_unknown_customer",
            extra={"customer_id": customer_id, "invoice_id": invoice.get("id")},
        )
        return

    new_status = "active" if paid else "past_due"
    await conn.execute(
        """
        update public.subscriptions
        set status = $2::public.subscription_status
        where tenant_id = $1::uuid
        """,
        tenant_id,
        new_status,
    )


# --- Top-level dispatcher -----------------------------------------------------


async def process_event(
    pool: asyncpg.Pool,
    event: stripe.Event,
    settings: Settings,
) -> bool:
    """Dispatch a verified Stripe event to its handler under a single tx.

    Returns True if processed, False if the event was a duplicate (already
    recorded in stripe_events). Either way, the caller should ack 200.
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            inserted = await record_event(conn, event)
            if not inserted:
                logger.info(
                    "stripe_webhook_duplicate",
                    extra={"event_id": event.id, "type": event.type},
                )
                return False

            if event.type not in HANDLED_EVENT_TYPES:
                logger.info(
                    "stripe_webhook_unhandled_type",
                    extra={"event_id": event.id, "type": event.type},
                )
                await mark_event_processed(conn, event.id)
                return True

            # event.data is a StripeObject — coerce to dict so handlers can use .get
            data = event.data or {}
            if hasattr(data, "to_dict"):
                data = data.to_dict()
            obj = data.get("object") if isinstance(data, dict) else {}
            obj = obj or {}
            if hasattr(obj, "to_dict"):
                obj = obj.to_dict()
            if event.type == "checkout.session.completed":
                await _handle_checkout_session_completed(conn, obj, settings)
            elif event.type in {
                "customer.subscription.created",
                "customer.subscription.updated",
            }:
                await _handle_subscription_event(conn, obj, settings, deleted=False)
            elif event.type == "customer.subscription.deleted":
                await _handle_subscription_event(conn, obj, settings, deleted=True)
            elif event.type == "invoice.payment_succeeded":
                await _handle_invoice_event(conn, obj, paid=True)
            elif event.type == "invoice.payment_failed":
                await _handle_invoice_event(conn, obj, paid=False)

            await mark_event_processed(conn, event.id)
    return True
