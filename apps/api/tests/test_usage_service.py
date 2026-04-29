"""Tests for the usage service (counters, plan resolution, quota checks)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.tenant import PlanTier
from src.models.usage import PlanLimits, QuotaExceededError
from src.services.usage import UsageService, current_period_key, period_bounds


@pytest.mark.unit
def test_period_bounds_for_january():
    """January period rolls into February correctly."""
    start, end = period_bounds("2026-01")
    assert start.month == 1
    assert end.month == 2
    assert end.year == 2026


@pytest.mark.unit
def test_period_bounds_for_december():
    """December period rolls into next January correctly."""
    start, end = period_bounds("2026-12")
    assert start.month == 12 and start.year == 2026
    assert end.month == 1 and end.year == 2027


@pytest.mark.unit
def test_current_period_key_format():
    """Period key is YYYY-MM."""
    key = current_period_key()
    parts = key.split("-")
    assert len(parts) == 2
    assert len(parts[0]) == 4 and len(parts[1]) == 2


@pytest.mark.unit
def test_plan_limits_for_known_plans():
    """Known plans resolve to defined limits; unknown falls back to FREE."""
    free = PlanLimits.for_plan("free")
    pro = PlanLimits.for_plan("pro")
    bogus = PlanLimits.for_plan("nonexistent-plan")

    assert free.queries_per_month == 100
    assert pro.queries_per_month > free.queries_per_month
    assert bogus.queries_per_month == free.queries_per_month


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_plan_returns_free_when_no_subscription():
    """A tenant without a subscription record is treated as FREE."""
    subs = MagicMock()
    subs.find_one = AsyncMock(return_value=None)
    usage = MagicMock()

    service = UsageService(usage, subs)
    plan = await service.get_plan("tenant-1")

    assert plan == PlanTier.FREE.value


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_plan_treats_cancelled_as_free():
    """Cancelled / past_due subscriptions are not entitled to paid limits."""
    subs = MagicMock()
    subs.find_one = AsyncMock(return_value={"plan": "pro", "status": "cancelled"})
    usage = MagicMock()

    service = UsageService(usage, subs)
    plan = await service.get_plan("tenant-1")

    assert plan == PlanTier.FREE.value


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_plan_returns_active_pro():
    """Active subscriptions return their plan."""
    subs = MagicMock()
    subs.find_one = AsyncMock(return_value={"plan": "pro", "status": "active"})

    service = UsageService(MagicMock(), subs)
    plan = await service.get_plan("tenant-1")

    assert plan == "pro"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_query_quota_under_limit_passes():
    """Query reservation succeeds when count stays under the cap."""
    usage_col = MagicMock()
    usage_col.find_one_and_update = AsyncMock(
        return_value={
            "tenant_id": "t",
            "period_key": "2026-04",
            "period_start": __import__("datetime").datetime(2026, 4, 1),
            "period_end": __import__("datetime").datetime(2026, 5, 1),
            "queries_count": 5,
        }
    )
    subs = MagicMock()
    subs.find_one = AsyncMock(return_value={"plan": "free", "status": "active"})

    service = UsageService(usage_col, subs)
    await service.check_query_quota("t")  # Should not raise


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_query_quota_over_limit_rolls_back_and_raises():
    """When the increment crosses the limit, it is reverted and 429 is raised."""
    from datetime import datetime, timezone

    usage_col = MagicMock()
    usage_col.find_one_and_update = AsyncMock(
        return_value={
            "tenant_id": "t",
            "period_key": "2026-04",
            "period_start": datetime(2026, 4, 1, tzinfo=timezone.utc),
            "period_end": datetime(2026, 5, 1, tzinfo=timezone.utc),
            "queries_count": 101,  # exceeds free.queries_per_month=100
        }
    )
    usage_col.update_one = AsyncMock()
    subs = MagicMock()
    subs.find_one = AsyncMock(return_value={"plan": "free", "status": "active"})

    service = UsageService(usage_col, subs)

    with pytest.raises(QuotaExceededError) as exc_info:
        await service.check_query_quota("t")

    assert exc_info.value.metric == "queries_per_month"
    assert exc_info.value.limit == 100
    # Confirm rollback was issued
    assert usage_col.update_one.await_count == 1
    rollback_call = usage_col.update_one.await_args
    assert rollback_call.args[1] == {"$inc": {"queries_count": -1}}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_document_quota_blocks_when_at_cap():
    """Document quota raises before insert when tenant is at the cap."""
    subs = MagicMock()
    subs.find_one = AsyncMock(return_value={"plan": "free", "status": "active"})
    service = UsageService(MagicMock(), subs)

    # Free plan documents_max=10
    with pytest.raises(QuotaExceededError) as exc_info:
        await service.check_document_quota("t", current_document_count=10)

    assert exc_info.value.metric == "documents_max"
    assert exc_info.value.limit == 10


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_document_quota_passes_under_cap():
    """Document quota accepts the upload while under the cap."""
    subs = MagicMock()
    subs.find_one = AsyncMock(return_value={"plan": "free", "status": "active"})
    service = UsageService(MagicMock(), subs)

    # Should not raise at 9/10
    await service.check_document_quota("t", current_document_count=9)
