"""Tests for the BillingService — Stripe customer + checkout creation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.billing import ModelTier
from src.models.tenant import PlanTier
from src.services.billing import BillingError, BillingService, is_safe_redirect_url


def _make_settings(**overrides):
    settings = MagicMock()
    settings.stripe_secret_key = "sk_test_dummy"
    settings.stripe_price_pro_starter = "price_pro_starter"
    settings.stripe_price_pro_standard = "price_pro_standard"
    settings.stripe_price_pro_premium = "price_pro_premium"
    settings.stripe_price_pro_ultra = None  # intentionally unset
    settings.stripe_price_enterprise_starter = "price_ent_starter"
    settings.stripe_price_enterprise_standard = "price_ent_standard"
    settings.stripe_price_enterprise_premium = "price_ent_premium"
    settings.stripe_price_enterprise_ultra = "price_ent_ultra"
    for k, v in overrides.items():
        setattr(settings, k, v)
    return settings


def _make_service():
    return BillingService(
        settings=_make_settings(),
        subscriptions_collection=MagicMock(),
        tenants_collection=MagicMock(),
        users_collection=MagicMock(),
    )


@pytest.mark.unit
def test_service_requires_stripe_secret_key():
    """Constructing without a key raises BillingError."""
    settings = _make_settings(stripe_secret_key=None)
    with pytest.raises(BillingError):
        BillingService(
            settings=settings,
            subscriptions_collection=MagicMock(),
            tenants_collection=MagicMock(),
            users_collection=MagicMock(),
        )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_or_create_customer_returns_existing():
    """If subscriptions already has a customer id, reuse it."""
    service = _make_service()
    service._subscriptions.find_one = AsyncMock(
        return_value={"tenant_id": "t1", "stripe_customer_id": "cus_existing"}
    )
    cid = await service.get_or_create_customer("t1")
    assert cid == "cus_existing"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_or_create_customer_creates_when_missing():
    """When no customer id exists, call Stripe and persist the new id."""
    service = _make_service()
    service._subscriptions.find_one = AsyncMock(return_value=None)
    service._users.find_one = AsyncMock(
        return_value={"tenant_id": "t1", "email": "owner@example.com", "role": "owner"}
    )
    service._subscriptions.update_one = AsyncMock()

    fake_customer = MagicMock(id="cus_new")
    with patch("src.services.billing.stripe.Customer.create", return_value=fake_customer):
        cid = await service.get_or_create_customer("t1")

    assert cid == "cus_new"
    service._subscriptions.update_one.assert_awaited()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_checkout_rejects_free_plan():
    """Free plan is not purchaseable."""
    service = _make_service()
    with pytest.raises(BillingError):
        await service.create_checkout_session(
            tenant_id="t1",
            plan=PlanTier.FREE,
            model_tier=ModelTier.STARTER,
            success_url="https://app/ok",
            cancel_url="https://app/cancel",
        )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_checkout_rejects_unconfigured_price():
    """Pro+Ultra has no price ID configured in the fixture — must fail."""
    service = _make_service()
    service._subscriptions.find_one = AsyncMock(
        return_value={"tenant_id": "t1", "stripe_customer_id": "cus_existing"}
    )
    with pytest.raises(BillingError, match="No Stripe price configured"):
        await service.create_checkout_session(
            tenant_id="t1",
            plan=PlanTier.PRO,
            model_tier=ModelTier.ULTRA,
            success_url="https://app/ok",
            cancel_url="https://app/cancel",
        )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_checkout_returns_url_and_session_id():
    """Happy path: returns the Stripe URL and session id."""
    service = _make_service()
    service._subscriptions.find_one = AsyncMock(
        return_value={"tenant_id": "t1", "stripe_customer_id": "cus_existing"}
    )

    fake_session = MagicMock(id="cs_test_123", url="https://checkout.stripe.com/c/cs_test_123")
    with patch(
        "src.services.billing.stripe.checkout.Session.create",
        return_value=fake_session,
    ) as mocked:
        url, sid = await service.create_checkout_session(
            tenant_id="t1",
            plan=PlanTier.PRO,
            model_tier=ModelTier.STARTER,
            success_url="https://app/ok",
            cancel_url="https://app/cancel",
        )
        # Assert the Stripe API was called with the right price ID and metadata.
        kwargs = mocked.call_args.kwargs
        assert kwargs["customer"] == "cus_existing"
        assert kwargs["line_items"] == [{"price": "price_pro_starter", "quantity": 1}]
        assert kwargs["mode"] == "subscription"
        assert kwargs["metadata"]["tenant_id"] == "t1"
        assert kwargs["metadata"]["plan"] == "pro"
        assert kwargs["metadata"]["model_tier"] == "starter"
        assert "idempotency_key" in kwargs

    assert url == "https://checkout.stripe.com/c/cs_test_123"
    assert sid == "cs_test_123"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_checkout_propagates_stripe_error():
    """Stripe SDK errors become BillingErrors."""
    import stripe

    service = _make_service()
    service._subscriptions.find_one = AsyncMock(
        return_value={"tenant_id": "t1", "stripe_customer_id": "cus_existing"}
    )

    with patch(
        "src.services.billing.stripe.checkout.Session.create",
        side_effect=stripe.StripeError("boom"),
    ):
        with pytest.raises(BillingError, match="checkout creation failed"):
            await service.create_checkout_session(
                tenant_id="t1",
                plan=PlanTier.PRO,
                model_tier=ModelTier.STARTER,
                success_url="https://app/ok",
                cancel_url="https://app/cancel",
            )


@pytest.mark.unit
def test_is_safe_redirect_url_https_allowed_host():
    assert is_safe_redirect_url("https://app.example.com/x", ["app.example.com"]) is True


@pytest.mark.unit
def test_is_safe_redirect_url_https_unknown_host():
    assert is_safe_redirect_url("https://evil.example.com/x", ["app.example.com"]) is False


@pytest.mark.unit
def test_is_safe_redirect_url_http_only_localhost():
    assert is_safe_redirect_url("http://localhost:3100/x", []) is True
    assert is_safe_redirect_url("http://example.com/x", ["example.com"]) is False


@pytest.mark.unit
def test_is_safe_redirect_url_rejects_other_schemes():
    assert is_safe_redirect_url("javascript:alert(1)", ["app.example.com"]) is False
    assert is_safe_redirect_url("ftp://app.example.com/", ["app.example.com"]) is False
    assert is_safe_redirect_url("", ["app.example.com"]) is False
    assert is_safe_redirect_url(None, ["app.example.com"]) is False
