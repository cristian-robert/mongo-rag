"""Tenant-scoped usage metering with atomic counters.

Counters are stored per (tenant_id, period_key) where period_key is
the calendar month in `YYYY-MM` form. Increments use `$inc` for
race-free updates; quota checks happen *after* increment so concurrent
requests cannot bypass the limit (the over-counting is bounded by
in-flight requests and is reverted on hard-block paths).

Document and chunk counts are *gauges*: they can also be sourced from
collection counts when accuracy matters more than speed (the wiki
documents this trade-off).
"""

import logging
from calendar import monthrange
from datetime import datetime, timezone
from typing import Any, Optional, cast

from pymongo import ReturnDocument
from pymongo.asynchronous.collection import AsyncCollection

from src.models.tenant import PlanTier
from src.models.usage import PlanLimits, QuotaExceededError, UsageRecord

logger = logging.getLogger(__name__)


WARNING_THRESHOLD = 0.80


def current_period_key(now: Optional[datetime] = None) -> str:
    """Return the YYYY-MM key for the given UTC instant (default: now)."""
    now = now or datetime.now(timezone.utc)
    return now.strftime("%Y-%m")


def period_bounds(period_key: str) -> tuple[datetime, datetime]:
    """Return the [start, end) UTC datetimes for a YYYY-MM period."""
    year, month = (int(p) for p in period_key.split("-"))
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    last_day = monthrange(year, month)[1]
    # End is exclusive — first instant of the next month would be
    # year+1/Jan when month == 12.
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    _ = last_day  # silence linter; included for clarity
    return start, end


class UsageService:
    """Tenant-scoped usage counters and quota checks."""

    def __init__(
        self,
        usage_collection: AsyncCollection,
        subscriptions_collection: AsyncCollection,
    ) -> None:
        self.usage = usage_collection
        self.subscriptions = subscriptions_collection

    async def get_plan(self, tenant_id: str) -> str:
        """Return the active plan for the tenant.

        Falls back to FREE if no subscription record exists or status is
        non-active (cancelled/past_due treated as FREE).
        """
        sub = await self.subscriptions.find_one(
            {"tenant_id": tenant_id},
            projection={"plan": 1, "status": 1},
        )
        if not sub:
            return PlanTier.FREE.value
        if sub.get("status") not in ("active", "trialing"):
            return PlanTier.FREE.value
        return sub.get("plan") or PlanTier.FREE.value

    async def get_or_create_period(
        self, tenant_id: str, period_key: Optional[str] = None
    ) -> dict[str, Any]:
        """Atomically fetch or create the usage record for the current period."""
        period_key = period_key or current_period_key()
        start, end = period_bounds(period_key)
        now = datetime.now(timezone.utc)

        doc = await self.usage.find_one_and_update(
            {"tenant_id": tenant_id, "period_key": period_key},
            {
                "$setOnInsert": {
                    "tenant_id": tenant_id,
                    "period_key": period_key,
                    "period_start": start,
                    "period_end": end,
                    "queries_count": 0,
                    "documents_count": 0,
                    "chunks_count": 0,
                    "embedding_tokens_count": 0,
                    "created_at": now,
                },
                "$set": {"updated_at": now},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        # upsert=True with return_document=AFTER always yields a doc.
        return cast(dict[str, Any], doc)

    async def increment(
        self,
        tenant_id: str,
        *,
        queries: int = 0,
        documents: int = 0,
        chunks: int = 0,
        embedding_tokens: int = 0,
    ) -> dict[str, Any]:
        """Atomically increment counters; create the period record if missing.

        Returns the post-increment usage document.
        """
        period_key = current_period_key()
        start, end = period_bounds(period_key)
        now = datetime.now(timezone.utc)

        inc: dict = {}
        if queries:
            inc["queries_count"] = queries
        if documents:
            inc["documents_count"] = documents
        if chunks:
            inc["chunks_count"] = chunks
        if embedding_tokens:
            inc["embedding_tokens_count"] = embedding_tokens

        update: dict = {
            "$setOnInsert": {
                "tenant_id": tenant_id,
                "period_key": period_key,
                "period_start": start,
                "period_end": end,
                "created_at": now,
            },
            "$set": {"updated_at": now},
        }
        if inc:
            update["$inc"] = inc

        doc = await self.usage.find_one_and_update(
            {"tenant_id": tenant_id, "period_key": period_key},
            update,
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return cast(dict[str, Any], doc)

    async def check_query_quota(self, tenant_id: str) -> None:
        """Reserve one query against the monthly quota.

        Atomically increments `queries_count` and, if the post-increment
        value exceeds the plan limit, decrements it back and raises
        `QuotaExceededError`. The reservation pattern guarantees no
        concurrent request can bypass the limit.
        """
        plan = await self.get_plan(tenant_id)
        limits = PlanLimits.for_plan(plan)

        if limits.queries_per_month <= 0:
            return

        doc = await self.increment(tenant_id, queries=1)
        used = doc.get("queries_count", 0)

        if used > limits.queries_per_month:
            # Roll back — this request will not be processed.
            await self.usage.update_one(
                {"tenant_id": tenant_id, "period_key": doc["period_key"]},
                {"$inc": {"queries_count": -1}},
            )
            seconds_until_reset = max(
                int((doc["period_end"] - datetime.now(timezone.utc)).total_seconds()),
                1,
            )
            raise QuotaExceededError(
                "queries_per_month",
                used=used - 1,
                limit=limits.queries_per_month,
                retry_after=seconds_until_reset,
            )

    async def check_document_quota(self, tenant_id: str, current_document_count: int) -> None:
        """Block document creation if the tenant is at or above the cap.

        Document/chunk caps are checked *before* mutation since they
        come from a separate collection. The caller passes the current
        live count.
        """
        plan = await self.get_plan(tenant_id)
        limits = PlanLimits.for_plan(plan)

        if limits.documents_max <= 0:
            return

        if current_document_count >= limits.documents_max:
            raise QuotaExceededError(
                "documents_max",
                used=current_document_count,
                limit=limits.documents_max,
            )

    @staticmethod
    def to_record(doc: dict) -> UsageRecord:
        """Convert a Mongo doc to a UsageRecord (for response shaping)."""
        return UsageRecord(
            tenant_id=doc["tenant_id"],
            period_key=doc["period_key"],
            period_start=doc["period_start"],
            period_end=doc["period_end"],
            queries_count=doc.get("queries_count", 0),
            documents_count=doc.get("documents_count", 0),
            chunks_count=doc.get("chunks_count", 0),
            embedding_tokens_count=doc.get("embedding_tokens_count", 0),
            created_at=doc.get("created_at", doc["period_start"]),
            updated_at=doc.get("updated_at", doc["period_start"]),
        )
