"""Usage metering and rate limiting models."""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from src.models.tenant import PlanTier


class PlanLimits(BaseModel):
    """Resource and rate limits for a subscription plan.

    All counts are per current monthly billing period unless suffixed
    `_per_minute`. Negative or zero values mean unlimited / disabled.
    """

    queries_per_month: int = Field(..., description="Max chat queries per period")
    documents_max: int = Field(..., description="Max active documents at any time")
    chunks_max: int = Field(..., description="Max stored chunks at any time")
    requests_per_minute: int = Field(..., description="Per-API-key request rate limit")
    embedding_tokens_per_month: int = Field(..., description="Max embedding tokens per period")

    @classmethod
    def for_plan(cls, plan: str) -> "PlanLimits":
        """Return limits for the named plan, falling back to FREE."""
        try:
            tier = PlanTier(plan)
        except ValueError:
            tier = PlanTier.FREE
        return _PLAN_LIMITS.get(tier, _PLAN_LIMITS[PlanTier.FREE])


_PLAN_LIMITS: dict[PlanTier, PlanLimits] = {
    PlanTier.FREE: PlanLimits(
        queries_per_month=100,
        documents_max=10,
        chunks_max=1_000,
        requests_per_minute=60,
        embedding_tokens_per_month=50_000,
    ),
    PlanTier.STARTER: PlanLimits(
        queries_per_month=2_000,
        documents_max=100,
        chunks_max=20_000,
        requests_per_minute=120,
        embedding_tokens_per_month=500_000,
    ),
    PlanTier.PRO: PlanLimits(
        queries_per_month=10_000,
        documents_max=1_000,
        chunks_max=200_000,
        requests_per_minute=300,
        embedding_tokens_per_month=5_000_000,
    ),
    PlanTier.ENTERPRISE: PlanLimits(
        queries_per_month=1_000_000,
        documents_max=100_000,
        chunks_max=20_000_000,
        requests_per_minute=1_000,
        embedding_tokens_per_month=500_000_000,
    ),
}


class UsageRecord(BaseModel):
    """Per-tenant per-period usage counters.

    A new document is created at the start of each billing period.
    `period_key` is `YYYY-MM` for monthly periods.
    """

    tenant_id: str
    period_key: str
    period_start: datetime
    period_end: datetime
    queries_count: int = 0
    documents_count: int = 0
    chunks_count: int = 0
    embedding_tokens_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UsageMetric(BaseModel):
    """A single usage metric returned by the usage endpoint."""

    used: int
    limit: int
    percent: float
    warning: bool
    blocked: bool


class UsageResponse(BaseModel):
    """Response for GET /api/v1/usage."""

    tenant_id: str
    plan: str
    period_key: str
    period_start: datetime
    period_end: datetime
    queries: UsageMetric
    documents: UsageMetric
    chunks: UsageMetric
    embedding_tokens: UsageMetric
    rate_limit_per_minute: int


class QuotaExceededError(Exception):
    """Raised when a tenant exceeds a hard quota."""

    def __init__(self, metric: str, used: int, limit: int, retry_after: Optional[int] = None):
        self.metric = metric
        self.used = used
        self.limit = limit
        self.retry_after = retry_after
        super().__init__(f"Quota exceeded for {metric}: {used}/{limit}")
