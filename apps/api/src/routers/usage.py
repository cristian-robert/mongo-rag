"""Usage and quota inspection endpoints."""

import logging

from fastapi import APIRouter, Depends

from src.core.dependencies import AgentDependencies
from src.core.deps import get_deps
from src.core.tenant import get_tenant_id_from_jwt
from src.models.usage import PlanLimits, UsageMetric, UsageResponse
from src.services.usage import WARNING_THRESHOLD, UsageService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["usage"])


def _metric(used: int, limit: int) -> UsageMetric:
    """Build a UsageMetric with derived percent / warning / blocked flags."""
    if limit <= 0:
        return UsageMetric(used=used, limit=limit, percent=0.0, warning=False, blocked=False)
    percent = round(used / limit, 4)
    return UsageMetric(
        used=used,
        limit=limit,
        percent=percent,
        warning=percent >= WARNING_THRESHOLD and percent < 1.0,
        blocked=percent >= 1.0,
    )


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    deps: AgentDependencies = Depends(get_deps),
) -> UsageResponse:
    """Return the current period's usage and plan limits for the tenant.

    JWT-only (dashboard endpoint) — API keys cannot inspect usage.
    """
    service = UsageService(deps.usage_collection, deps.subscriptions_collection)
    plan = await service.get_plan(tenant_id)
    limits = PlanLimits.for_plan(plan)
    record = await service.get_or_create_period(tenant_id)

    # Document and chunk counts come from live collections so the gauge
    # is correct even if increment hooks ever miss a write.
    docs_used = await deps.documents_collection.count_documents({"tenant_id": tenant_id})
    chunks_used = await deps.chunks_collection.count_documents({"tenant_id": tenant_id})

    return UsageResponse(
        tenant_id=tenant_id,
        plan=plan,
        period_key=record["period_key"],
        period_start=record["period_start"],
        period_end=record["period_end"],
        queries=_metric(record.get("queries_count", 0), limits.queries_per_month),
        documents=_metric(docs_used, limits.documents_max),
        chunks=_metric(chunks_used, limits.chunks_max),
        embedding_tokens=_metric(
            record.get("embedding_tokens_count", 0), limits.embedding_tokens_per_month
        ),
        rate_limit_per_minute=limits.requests_per_minute,
    )
