"""Tests for the billing router endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from tests.conftest import make_auth_header


@pytest.fixture
def billing_client(mock_deps):
    """Test client with billing-ready mocked deps (Stripe configured)."""
    from src.main import app

    mock_deps.subscriptions_collection = MagicMock()
    mock_deps.users_collection = MagicMock()
    mock_deps.tenants_collection = MagicMock()
    settings = MagicMock()
    settings.stripe_secret_key = "sk_test_dummy"
    settings.stripe_price_pro_starter = "price_pro_starter"
    settings.stripe_price_pro_standard = "price_pro_standard"
    settings.stripe_price_pro_premium = "price_pro_premium"
    settings.stripe_price_pro_ultra = "price_pro_ultra"
    settings.stripe_price_enterprise_starter = "price_ent_starter"
    settings.stripe_price_enterprise_standard = "price_ent_standard"
    settings.stripe_price_enterprise_premium = "price_ent_premium"
    settings.stripe_price_enterprise_ultra = "price_ent_ultra"
    mock_deps.settings = settings

    with TestClient(app) as c:
        app.state.deps = mock_deps
        yield c


@pytest.mark.unit
def test_list_plans_is_public(billing_client):
    """GET /api/v1/billing/plans returns the catalog without auth."""
    response = billing_client.get("/api/v1/billing/plans")
    assert response.status_code == 200
    data = response.json()
    assert "plans" in data
    assert "model_tiers" in data

    plan_names = {p["plan"] for p in data["plans"]}
    assert {"free", "starter", "pro", "enterprise"} <= plan_names

    # Each model tier should have at least one model.
    for tier in data["model_tiers"]:
        assert len(tier["models"]) >= 1


@pytest.mark.unit
def test_checkout_requires_auth(billing_client):
    """POST /api/v1/billing/checkout returns 401 without auth header."""
    response = billing_client.post(
        "/api/v1/billing/checkout",
        json={
            "plan": "pro",
            "model_tier": "starter",
            "success_url": "https://app.example.com/billing/success",
            "cancel_url": "https://app.example.com/billing/cancel",
        },
    )
    assert response.status_code == 401


@pytest.mark.unit
def test_checkout_rejects_free_plan(billing_client):
    """Free plan cannot be checked out — 400."""
    response = billing_client.post(
        "/api/v1/billing/checkout",
        headers=make_auth_header(),
        json={
            "plan": "free",
            "model_tier": "starter",
            "success_url": "https://app.example.com/ok",
            "cancel_url": "https://app.example.com/cancel",
        },
    )
    assert response.status_code == 400


@pytest.mark.unit
def test_checkout_rejects_invalid_url_scheme(billing_client):
    """Non-https success URLs are rejected outside localhost."""
    response = billing_client.post(
        "/api/v1/billing/checkout",
        headers=make_auth_header(),
        json={
            "plan": "pro",
            "model_tier": "starter",
            "success_url": "ftp://example.com/ok",
            "cancel_url": "https://app.example.com/cancel",
        },
    )
    assert response.status_code == 400


@pytest.mark.unit
def test_checkout_allows_localhost_http(billing_client):
    """Dev mode: http://localhost is allowed for success/cancel URLs."""
    with patch("src.routers.billing.BillingService") as mock_service:
        instance = mock_service.return_value
        instance.create_checkout_session = AsyncMock(
            return_value=("https://checkout.stripe.com/session_test", "cs_test_123")
        )
        response = billing_client.post(
            "/api/v1/billing/checkout",
            headers=make_auth_header(),
            json={
                "plan": "pro",
                "model_tier": "starter",
                "success_url": "http://localhost:3100/dashboard/billing/success",
                "cancel_url": "http://127.0.0.1:3100/dashboard/billing",
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["checkout_url"].startswith("https://checkout.stripe.com/")
    assert body["session_id"] == "cs_test_123"


@pytest.mark.unit
def test_checkout_returns_503_when_price_unconfigured(billing_client):
    """Missing price config surfaces as 503 (server config error)."""
    from src.services.billing import BillingError

    with patch("src.routers.billing.BillingService") as mock_service:
        instance = mock_service.return_value
        instance.create_checkout_session = AsyncMock(
            side_effect=BillingError("No Stripe price configured for plan=pro model_tier=ultra")
        )
        response = billing_client.post(
            "/api/v1/billing/checkout",
            headers=make_auth_header(),
            json={
                "plan": "pro",
                "model_tier": "ultra",
                "success_url": "https://app.example.com/ok",
                "cancel_url": "https://app.example.com/cancel",
            },
        )
    assert response.status_code == 503


@pytest.mark.unit
def test_checkout_returns_400_on_stripe_error(billing_client):
    """Stripe-side BillingError surfaces as 400."""
    from src.services.billing import BillingError

    with patch("src.routers.billing.BillingService") as mock_service:
        instance = mock_service.return_value
        instance.create_checkout_session = AsyncMock(
            side_effect=BillingError("Stripe checkout creation failed: card_declined")
        )
        response = billing_client.post(
            "/api/v1/billing/checkout",
            headers=make_auth_header(),
            json={
                "plan": "pro",
                "model_tier": "starter",
                "success_url": "https://app.example.com/ok",
                "cancel_url": "https://app.example.com/cancel",
            },
        )
    assert response.status_code == 400


@pytest.mark.unit
def test_checkout_rejects_api_key_auth(billing_client):
    """Billing endpoints reject API key auth — JWT only."""
    response = billing_client.post(
        "/api/v1/billing/checkout",
        headers={"Authorization": "Bearer mrag_fake_api_key"},
        json={
            "plan": "pro",
            "model_tier": "starter",
            "success_url": "https://app.example.com/ok",
            "cancel_url": "https://app.example.com/cancel",
        },
    )
    assert response.status_code == 403


@pytest.mark.unit
def test_checkout_503_when_stripe_not_configured(mock_deps):
    """If STRIPE_SECRET_KEY missing, /checkout returns 503."""
    from src.main import app

    mock_deps.subscriptions_collection = MagicMock()
    mock_deps.users_collection = MagicMock()
    mock_deps.tenants_collection = MagicMock()
    settings = MagicMock()
    settings.stripe_secret_key = None
    mock_deps.settings = settings

    with TestClient(app) as c:
        app.state.deps = mock_deps
        response = c.post(
            "/api/v1/billing/checkout",
            headers=make_auth_header(),
            json={
                "plan": "pro",
                "model_tier": "starter",
                "success_url": "https://app.example.com/ok",
                "cancel_url": "https://app.example.com/cancel",
            },
        )
    assert response.status_code == 503
