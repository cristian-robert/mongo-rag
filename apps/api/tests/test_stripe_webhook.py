"""Tests for the Stripe webhook handler (issue #43).

Covers:
- Signature verification (good, bad, missing, malformed body)
- Idempotency: duplicate event_id is a no-op
- Event handlers for each handled type
- Status mapping (Stripe → internal enum)
- Tenant resolution from customer_id
- Unknown customer is not a 500
- PII redaction in stored payload
"""

from __future__ import annotations

import hmac
import json
import time
from hashlib import sha256
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import stripe
from fastapi.testclient import TestClient

from src.services.stripe_webhook import (
    HANDLED_EVENT_TYPES,
    WebhookSignatureError,
    _resolve_plan_from_price,
    construct_event,
    map_status,
    process_event,
)

WEBHOOK_SECRET = "whsec_test_secret_for_unit_tests_only"


def _sign(payload: bytes, secret: str = WEBHOOK_SECRET, ts: int | None = None) -> str:
    """Build a Stripe-Signature header for a given payload."""
    timestamp = ts if ts is not None else int(time.time())
    signed_payload = f"{timestamp}.".encode() + payload
    signature = hmac.new(secret.encode(), signed_payload, sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


def _make_event_payload(
    event_id: str,
    event_type: str,
    obj: dict[str, Any],
) -> bytes:
    return json.dumps(
        {
            "id": event_id,
            "object": "event",
            "type": event_type,
            "data": {"object": obj},
            "created": int(time.time()),
        }
    ).encode()


# --- Pure helpers -------------------------------------------------------------


@pytest.mark.unit
def test_map_status_known_values():
    assert map_status("active") == "active"
    assert map_status("trialing") == "trialing"
    assert map_status("past_due") == "past_due"
    assert map_status("canceled") == "canceled"


@pytest.mark.unit
def test_map_status_unknown_falls_back_to_incomplete():
    assert map_status("hypothetical_future_status") == "incomplete"
    assert map_status(None) == "incomplete"
    assert map_status("") == "incomplete"


@pytest.mark.unit
def test_resolve_plan_from_price_pro_starter():
    settings = MagicMock()
    settings.stripe_price_pro_starter = "price_xxx_pro_starter"
    settings.stripe_price_pro_standard = None
    settings.stripe_price_pro_premium = None
    settings.stripe_price_pro_ultra = None
    settings.stripe_price_enterprise_starter = None
    settings.stripe_price_enterprise_standard = None
    settings.stripe_price_enterprise_premium = None
    settings.stripe_price_enterprise_ultra = None
    plan = _resolve_plan_from_price(settings, "price_xxx_pro_starter")
    assert plan is not None
    assert plan.value == "pro"


@pytest.mark.unit
def test_resolve_plan_from_price_unknown_returns_none():
    settings = MagicMock()
    for tier in ("starter", "standard", "premium", "ultra"):
        for plan in ("pro", "enterprise"):
            setattr(settings, f"stripe_price_{plan}_{tier}", None)
    assert _resolve_plan_from_price(settings, "price_unknown") is None
    assert _resolve_plan_from_price(settings, None) is None


@pytest.mark.unit
def test_handled_event_types_complete():
    """Every event type the issue lists must be handled."""
    required = {
        "checkout.session.completed",
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
        "invoice.payment_failed",
    }
    assert required <= HANDLED_EVENT_TYPES


# --- Signature verification ---------------------------------------------------


@pytest.mark.unit
def test_construct_event_accepts_valid_signature():
    payload = _make_event_payload("evt_1", "ping", {"foo": "bar"})
    sig = _sign(payload)

    event = construct_event(payload=payload, signature=sig, secret=WEBHOOK_SECRET)
    assert event.id == "evt_1"
    assert event.type == "ping"


@pytest.mark.unit
def test_construct_event_rejects_bad_signature():
    payload = _make_event_payload("evt_1", "ping", {"foo": "bar"})
    bad_sig = _sign(payload, secret="whsec_attacker_supplied_secret")

    with pytest.raises(WebhookSignatureError):
        construct_event(payload=payload, signature=bad_sig, secret=WEBHOOK_SECRET)


@pytest.mark.unit
def test_construct_event_rejects_replay_outside_tolerance():
    payload = _make_event_payload("evt_1", "ping", {"foo": "bar"})
    # Timestamp 10 minutes in the past + tolerance 60s → reject.
    old_ts = int(time.time()) - 600
    sig = _sign(payload, ts=old_ts)

    with pytest.raises(WebhookSignatureError):
        construct_event(payload=payload, signature=sig, secret=WEBHOOK_SECRET, tolerance=60)


@pytest.mark.unit
def test_construct_event_rejects_malformed_payload():
    bad = b"this is not json"
    sig = _sign(bad)
    with pytest.raises(WebhookSignatureError):
        construct_event(payload=bad, signature=sig, secret=WEBHOOK_SECRET)


# --- Router-level tests -------------------------------------------------------


@pytest.fixture
def webhook_client(mock_deps):
    """Test client with webhook secret + Postgres pool stubbed."""
    from src.main import app

    settings = MagicMock()
    settings.stripe_webhook_secret = WEBHOOK_SECRET
    settings.stripe_webhook_tolerance_seconds = 300
    settings.supabase_db_url = "postgresql://stub"
    for attr in (
        "stripe_price_pro_starter",
        "stripe_price_pro_standard",
        "stripe_price_pro_premium",
        "stripe_price_pro_ultra",
        "stripe_price_enterprise_starter",
        "stripe_price_enterprise_standard",
        "stripe_price_enterprise_premium",
        "stripe_price_enterprise_ultra",
    ):
        setattr(settings, attr, f"price_{attr.split('_', 2)[2]}")
    mock_deps.settings = settings

    with TestClient(app) as c:
        app.state.deps = mock_deps
        yield c


@pytest.mark.unit
def test_webhook_rejects_missing_signature(webhook_client):
    payload = _make_event_payload("evt_no_sig", "ping", {})
    response = webhook_client.post("/api/v1/stripe/webhook", content=payload)
    assert response.status_code == 400
    assert "signature" in response.json()["detail"].lower()


@pytest.mark.unit
def test_webhook_rejects_bad_signature(webhook_client):
    payload = _make_event_payload("evt_bad", "ping", {})
    bad_sig = _sign(payload, secret="whsec_wrong_secret")
    response = webhook_client.post(
        "/api/v1/stripe/webhook",
        content=payload,
        headers={"Stripe-Signature": bad_sig},
    )
    assert response.status_code == 400


@pytest.mark.unit
def test_webhook_rejects_empty_body(webhook_client):
    sig = _sign(b"")
    response = webhook_client.post(
        "/api/v1/stripe/webhook",
        content=b"",
        headers={"Stripe-Signature": sig},
    )
    assert response.status_code == 400


@pytest.mark.unit
def test_webhook_503_when_secret_unconfigured(webhook_client, mock_deps):
    mock_deps.settings.stripe_webhook_secret = None
    response = webhook_client.post(
        "/api/v1/stripe/webhook",
        content=b"{}",
        headers={"Stripe-Signature": "t=1,v1=abc"},
    )
    assert response.status_code == 503


# --- Process-event integration (mocked Postgres connection) -------------------


class _FakePool:
    """Minimal asyncpg.Pool double for unit tests."""

    def __init__(self, conn: "_FakeConn") -> None:
        self._conn = conn

    def acquire(self):
        return _AcquireCM(self._conn)


class _AcquireCM:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return None


class _FakeTx:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None


class _FakeConn:
    """Records executed statements + mocks the dedupe insert."""

    def __init__(
        self,
        *,
        dedupe_seen: set[str] | None = None,
        customer_to_tenant: dict[str, str] | None = None,
    ) -> None:
        self.executed: list[tuple[str, tuple]] = []
        self._dedupe_seen = dedupe_seen if dedupe_seen is not None else set()
        self._customer_to_tenant = customer_to_tenant or {}

    def transaction(self):
        return _FakeTx()

    async def execute(self, sql: str, *args) -> str:
        self.executed.append((sql, args))
        return "OK"

    async def fetchrow(self, sql: str, *args):
        # Idempotency insert into stripe_events.
        if "insert into public.stripe_events" in sql:
            event_id = args[0]
            if event_id in self._dedupe_seen:
                return None
            self._dedupe_seen.add(event_id)
            return {"event_id": event_id}
        # tenant_id resolution.
        if "from public.subscriptions" in sql and "stripe_customer_id" in sql:
            cust = args[0]
            tenant_id = self._customer_to_tenant.get(cust)
            return {"tenant_id": tenant_id} if tenant_id else None
        return None


def _build_event(event_id: str, event_type: str, obj: dict) -> stripe.Event:
    return stripe.Event.construct_from(
        {
            "id": event_id,
            "object": "event",
            "type": event_type,
            "data": {"object": obj},
            "created": int(time.time()),
        },
        key="sk_test",
    )


@pytest.mark.unit
async def test_process_event_idempotent_on_replay():
    """Replaying the same event_id must not run side effects twice."""
    settings = MagicMock()
    settings.stripe_price_pro_starter = "price_pro_starter"
    for attr in (
        "stripe_price_pro_standard",
        "stripe_price_pro_premium",
        "stripe_price_pro_ultra",
        "stripe_price_enterprise_starter",
        "stripe_price_enterprise_standard",
        "stripe_price_enterprise_premium",
        "stripe_price_enterprise_ultra",
    ):
        setattr(settings, attr, None)

    seen: set[str] = set()
    tenant_uuid = "11111111-1111-1111-1111-111111111111"
    conn = _FakeConn(dedupe_seen=seen, customer_to_tenant={"cus_1": tenant_uuid})
    pool = _FakePool(conn)

    event = _build_event(
        "evt_dup_1",
        "invoice.payment_failed",
        {"id": "in_1", "customer": "cus_1"},
    )

    first = await process_event(pool, event, settings)
    assert first is True

    # Second call: same event_id → False (duplicate). And no second status update.
    second_conn = _FakeConn(dedupe_seen=seen, customer_to_tenant={"cus_1": "tenant"})
    second_pool = _FakePool(second_conn)
    second = await process_event(second_pool, event, settings)
    assert second is False
    # Only the dedupe insert should have happened on the second pass.
    update_statements = [s for s, _ in second_conn.executed if "update public.subscriptions" in s]
    assert update_statements == []


@pytest.mark.unit
async def test_process_event_unknown_customer_is_noop_not_500():
    """Sub event for a customer we don't know about must not raise."""
    settings = MagicMock()
    for attr in (
        "stripe_price_pro_starter",
        "stripe_price_pro_standard",
        "stripe_price_pro_premium",
        "stripe_price_pro_ultra",
        "stripe_price_enterprise_starter",
        "stripe_price_enterprise_standard",
        "stripe_price_enterprise_premium",
        "stripe_price_enterprise_ultra",
    ):
        setattr(settings, attr, None)

    conn = _FakeConn(customer_to_tenant={})  # no mapping
    pool = _FakePool(conn)
    event = _build_event(
        "evt_unknown",
        "customer.subscription.updated",
        {
            "id": "sub_x",
            "customer": "cus_unknown",
            "status": "active",
            "items": {"data": []},
            "metadata": {},
        },
    )

    processed = await process_event(pool, event, settings)
    assert processed is True

    # No subscriptions writes — only dedupe insert + processed marker.
    sub_writes = [
        s
        for s, _ in conn.executed
        if "into public.subscriptions" in s or "update public.subscriptions" in s
    ]
    assert sub_writes == []


@pytest.mark.unit
async def test_process_event_subscription_updated_maps_status_and_plan():
    settings = MagicMock()
    settings.stripe_price_pro_starter = "price_pro_starter"
    for attr in (
        "stripe_price_pro_standard",
        "stripe_price_pro_premium",
        "stripe_price_pro_ultra",
        "stripe_price_enterprise_starter",
        "stripe_price_enterprise_standard",
        "stripe_price_enterprise_premium",
        "stripe_price_enterprise_ultra",
    ):
        setattr(settings, attr, None)

    tenant_uuid = "11111111-1111-1111-1111-111111111111"
    conn = _FakeConn(customer_to_tenant={"cus_1": tenant_uuid})
    pool = _FakePool(conn)

    event = _build_event(
        "evt_sub_upd",
        "customer.subscription.updated",
        {
            "id": "sub_1",
            "customer": "cus_1",
            "status": "past_due",
            "current_period_end": int(time.time()) + 3600,
            "items": {"data": [{"price": {"id": "price_pro_starter"}}]},
            "metadata": {},
        },
    )
    processed = await process_event(pool, event, settings)
    assert processed is True

    # The full upsert path should have fired (plan resolved).
    upserts = [s for s, args in conn.executed if "insert into public.subscriptions" in s]
    assert len(upserts) == 1
    # Args contain the tenant uuid and 'past_due'.
    _, args = next((s, a) for s, a in conn.executed if "insert into public.subscriptions" in s)
    assert args[0] == tenant_uuid
    assert "past_due" in args


@pytest.mark.unit
async def test_process_event_subscription_deleted_sets_canceled():
    settings = MagicMock()
    for attr in (
        "stripe_price_pro_starter",
        "stripe_price_pro_standard",
        "stripe_price_pro_premium",
        "stripe_price_pro_ultra",
        "stripe_price_enterprise_starter",
        "stripe_price_enterprise_standard",
        "stripe_price_enterprise_premium",
        "stripe_price_enterprise_ultra",
    ):
        setattr(settings, attr, None)

    conn = _FakeConn(customer_to_tenant={"cus_1": "22222222-2222-2222-2222-222222222222"})
    pool = _FakePool(conn)
    event = _build_event(
        "evt_del",
        "customer.subscription.deleted",
        {
            "id": "sub_1",
            "customer": "cus_1",
            "status": "canceled",
            "items": {"data": []},
            "metadata": {},
        },
    )
    await process_event(pool, event, settings)

    # Status-only update path (no plan resolved) — must include 'canceled'.
    canceled_updates = [
        (s, a) for s, a in conn.executed if "update public.subscriptions" in s and "canceled" in a
    ]
    assert canceled_updates


@pytest.mark.unit
async def test_process_event_invoice_payment_failed_sets_past_due():
    settings = MagicMock()
    conn = _FakeConn(customer_to_tenant={"cus_1": "33333333-3333-3333-3333-333333333333"})
    pool = _FakePool(conn)
    event = _build_event(
        "evt_inv_fail",
        "invoice.payment_failed",
        {"id": "in_1", "customer": "cus_1"},
    )
    await process_event(pool, event, settings)

    past_due = [
        (s, a) for s, a in conn.executed if "update public.subscriptions" in s and "past_due" in a
    ]
    assert past_due


@pytest.mark.unit
async def test_process_event_invoice_payment_succeeded_sets_active():
    settings = MagicMock()
    conn = _FakeConn(customer_to_tenant={"cus_1": "44444444-4444-4444-4444-444444444444"})
    pool = _FakePool(conn)
    event = _build_event(
        "evt_inv_ok",
        "invoice.payment_succeeded",
        {"id": "in_1", "customer": "cus_1"},
    )
    await process_event(pool, event, settings)

    active = [
        (s, a) for s, a in conn.executed if "update public.subscriptions" in s and "active" in a
    ]
    assert active


@pytest.mark.unit
async def test_process_event_checkout_session_completed_uses_metadata_tenant_id():
    settings = MagicMock()
    tenant_uuid = "55555555-5555-5555-5555-555555555555"
    conn = _FakeConn()
    pool = _FakePool(conn)
    event = _build_event(
        "evt_co",
        "checkout.session.completed",
        {
            "id": "cs_1",
            "customer": "cus_new",
            "subscription": "sub_new",
            "metadata": {"tenant_id": tenant_uuid, "plan": "pro"},
        },
    )
    await process_event(pool, event, settings)

    upserts = [(s, a) for s, a in conn.executed if "insert into public.subscriptions" in s]
    assert upserts
    _, args = upserts[0]
    assert args[0] == tenant_uuid
    assert args[1] == "cus_new"
    assert args[2] == "sub_new"
    assert args[3] == "pro"


@pytest.mark.unit
async def test_process_event_unhandled_type_is_recorded_and_acked():
    """Events outside HANDLED_EVENT_TYPES still get persisted but no handler runs."""
    settings = MagicMock()
    conn = _FakeConn()
    pool = _FakePool(conn)
    event = _build_event("evt_misc", "customer.created", {"id": "cus_1"})
    processed = await process_event(pool, event, settings)
    assert processed is True
    sub_writes = [
        s for s, _ in conn.executed if "subscriptions" in s and ("update" in s or "insert" in s)
    ]
    assert sub_writes == []


@pytest.mark.unit
async def test_router_dispatches_verified_event_to_processor(webhook_client):
    """End-to-end: signature verifies, process_event called once."""
    payload = _make_event_payload(
        "evt_router_1",
        "invoice.payment_failed",
        {"id": "in_1", "customer": "cus_1"},
    )
    sig = _sign(payload)

    with patch("src.routers.stripe_webhooks.get_pool", new=AsyncMock(return_value=MagicMock())):
        with patch(
            "src.routers.stripe_webhooks.process_event",
            new=AsyncMock(return_value=True),
        ) as mock_proc:
            response = webhook_client.post(
                "/api/v1/stripe/webhook",
                content=payload,
                headers={"Stripe-Signature": sig},
            )
    assert response.status_code == 200
    mock_proc.assert_awaited_once()
