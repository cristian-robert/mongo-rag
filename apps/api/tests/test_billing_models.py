"""Unit tests for billing models, plan config, and price resolution."""

import pytest

from src.core.settings import Settings
from src.models.billing import (
    DISPLAY_PRICES_CENTS,
    MODEL_CATALOG,
    NON_CHECKOUT_PLANS,
    PLAN_LIMITS,
    ModelTier,
    resolve_stripe_price_id,
)
from src.models.tenant import PlanTier


@pytest.mark.unit
def test_plan_limits_cover_all_tiers():
    """Every PlanTier must have a quota entry."""
    for plan in PlanTier:
        assert plan in PLAN_LIMITS, f"PLAN_LIMITS missing entry for {plan}"
        entry = PLAN_LIMITS[plan]
        assert entry["queries_per_month"] > 0
        assert entry["documents"] > 0
        assert entry["bots"] > 0


@pytest.mark.unit
def test_plan_limits_strictly_increase():
    """Free < Starter < Pro < Enterprise on every quota dimension."""
    free = PLAN_LIMITS[PlanTier.FREE]
    starter = PLAN_LIMITS[PlanTier.STARTER]
    pro = PLAN_LIMITS[PlanTier.PRO]
    ent = PLAN_LIMITS[PlanTier.ENTERPRISE]
    for key in ("queries_per_month", "documents", "bots"):
        assert free[key] < starter[key] <= pro[key] < ent[key], (
            f"plan progression violated on {key}"
        )


@pytest.mark.unit
def test_model_catalog_every_tier_has_models():
    """Every ModelTier must have at least one model."""
    for tier in ModelTier:
        assert tier in MODEL_CATALOG
        assert len(MODEL_CATALOG[tier]) >= 1


@pytest.mark.unit
def test_model_catalog_no_duplicate_model_ids():
    """A model id must appear in exactly one tier."""
    seen: dict[str, ModelTier] = {}
    for tier, entries in MODEL_CATALOG.items():
        for mid, _, _ in entries:
            assert mid not in seen, f"{mid} appears in {seen[mid]} and {tier}"
            seen[mid] = tier


@pytest.mark.unit
def test_display_prices_cover_paid_combinations():
    """Every (Pro|Enterprise, ModelTier) combo has a display price."""
    for plan in (PlanTier.PRO, PlanTier.ENTERPRISE):
        for tier in ModelTier:
            assert (plan, tier) in DISPLAY_PRICES_CENTS


@pytest.mark.unit
def test_non_checkout_plans():
    """Free and Starter cannot be checked out via Stripe."""
    assert PlanTier.FREE in NON_CHECKOUT_PLANS
    assert PlanTier.STARTER in NON_CHECKOUT_PLANS
    assert PlanTier.PRO not in NON_CHECKOUT_PLANS
    assert PlanTier.ENTERPRISE not in NON_CHECKOUT_PLANS


@pytest.mark.unit
def test_resolve_stripe_price_id_when_configured():
    """resolve_stripe_price_id returns the configured value."""

    class _S:
        stripe_price_pro_starter = "price_abc123"
        stripe_price_pro_standard = None

    assert resolve_stripe_price_id(_S(), PlanTier.PRO, ModelTier.STARTER) == "price_abc123"
    assert resolve_stripe_price_id(_S(), PlanTier.PRO, ModelTier.STANDARD) is None


@pytest.mark.unit
def test_settings_accepts_stripe_env(monkeypatch):
    """Settings loads Stripe variables from the environment."""
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("LLM_API_KEY", "test")
    monkeypatch.setenv("EMBEDDING_API_KEY", "test")
    monkeypatch.setenv("NEXTAUTH_SECRET", "test-secret-for-unit-tests-minimum-32chars")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_xxx")
    monkeypatch.setenv("STRIPE_PRICE_PRO_STARTER", "price_pro_starter_test")

    s = Settings()
    assert s.stripe_secret_key == "sk_test_xxx"
    assert s.stripe_price_pro_starter == "price_pro_starter_test"
    # Combos that aren't set default to None.
    assert s.stripe_price_pro_ultra is None
