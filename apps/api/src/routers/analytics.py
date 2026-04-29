"""Analytics endpoints for the dashboard.

All endpoints are JWT-only (dashboard sessions). API keys are rejected so
analytics access can never be silently delegated to a third party who
holds an API key.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.core.dependencies import AgentDependencies
from src.core.deps import get_deps
from src.core.tenant import get_tenant_id_from_jwt
from src.models.analytics import (
    AnalyticsOverview,
    AnalyticsTimeseries,
    ConversationDetail,
    QueriesPage,
)
from src.services.analytics import (
    DEFAULT_PAGE_SIZE,
    DEFAULT_WINDOW_DAYS,
    MAX_PAGE_SIZE,
    MAX_WINDOW_DAYS,
    MIN_PAGE_SIZE,
    MIN_WINDOW_DAYS,
    AnalyticsService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOverview)
async def get_overview(
    days: int = Query(default=DEFAULT_WINDOW_DAYS, ge=MIN_WINDOW_DAYS, le=MAX_WINDOW_DAYS),
    bot_id: Optional[str] = Query(default=None, max_length=128),
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    deps: AgentDependencies = Depends(get_deps),
) -> AnalyticsOverview:
    """Aggregated counts, no-answer rate, top queries for the time window."""
    service = AnalyticsService(deps.conversations_collection)
    return await service.overview(tenant_id, window_days=days, bot_id=bot_id)


@router.get("/timeseries", response_model=AnalyticsTimeseries)
async def get_timeseries(
    days: int = Query(default=DEFAULT_WINDOW_DAYS, ge=MIN_WINDOW_DAYS, le=MAX_WINDOW_DAYS),
    bot_id: Optional[str] = Query(default=None, max_length=128),
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    deps: AgentDependencies = Depends(get_deps),
) -> AnalyticsTimeseries:
    """Daily volume of user queries and assistant responses."""
    service = AnalyticsService(deps.conversations_collection)
    return await service.timeseries(tenant_id, window_days=days, bot_id=bot_id)


@router.get("/queries", response_model=QueriesPage)
async def list_queries(
    days: int = Query(default=DEFAULT_WINDOW_DAYS, ge=MIN_WINDOW_DAYS, le=MAX_WINDOW_DAYS),
    page: int = Query(default=1, ge=1, le=10000),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=MIN_PAGE_SIZE, le=MAX_PAGE_SIZE),
    no_answer_only: bool = Query(default=False),
    bot_id: Optional[str] = Query(default=None, max_length=128),
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    deps: AgentDependencies = Depends(get_deps),
) -> QueriesPage:
    """Paginated user-query list with filters."""
    service = AnalyticsService(deps.conversations_collection)
    return await service.queries(
        tenant_id,
        window_days=days,
        page=page,
        page_size=page_size,
        no_answer_only=no_answer_only,
        bot_id=bot_id,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    deps: AgentDependencies = Depends(get_deps),
) -> ConversationDetail:
    """Full transcript for one conversation. 404 hides cross-tenant lookups."""
    if not conversation_id or len(conversation_id) > 128:
        raise HTTPException(status_code=404, detail="Conversation not found")
    service = AnalyticsService(deps.conversations_collection)
    detail = await service.conversation_detail(tenant_id, conversation_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return detail
