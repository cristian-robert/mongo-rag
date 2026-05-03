"""Bot configuration endpoints.

CRUD requires a JWT (dashboard sessions only). A separate public endpoint
exposes a non-secret subset of a bot for widget embedding.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from src.core.authz import Principal, require_role
from src.core.dependencies import AgentDependencies
from src.core.deps import get_deps
from src.models.api import MessageResponse
from src.models.bot import (
    BotListResponse,
    BotResponse,
    CreateBotRequest,
    PublicBotResponse,
    UpdateBotRequest,
    WidgetConfig,
)
from src.models.user import UserRole
from src.services.bot import BotService, BotSlugTakenError
from src.services.plan import get_tenant_plan, is_paid_plan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/bots", tags=["bots"])

# Bot count cap per tenant. Plan-based limits live in the billing layer; this
# is a hard ceiling to bound the slug index regardless of plan.
MAX_BOTS_PER_TENANT = 50


def _get_bot_service(deps: AgentDependencies = Depends(get_deps)) -> BotService:
    return BotService(bots_collection=deps.bots_collection)


async def _enforce_branding_plan_gate(
    widget_config: Optional[WidgetConfig],
    deps: AgentDependencies,
    tenant_id: str,
) -> None:
    """Reject ``branding_text`` writes from free-tier tenants.

    No-ops when ``widget_config`` is missing from the payload or when
    ``branding_text`` is unset. Reads the active plan from the Mongo
    ``subscriptions`` collection via ``get_tenant_plan``.
    """
    if widget_config is None or widget_config.branding_text is None:
        return
    plan = await get_tenant_plan(deps.subscriptions_collection, tenant_id)
    if not is_paid_plan(plan):
        logger.info(
            "bot_branding_text_blocked_free_tier",
            extra={"tenant_id": tenant_id, "plan": plan.value},
        )
        raise HTTPException(
            status_code=403,
            detail="branding_text requires a paid plan",
        )


@router.post("", response_model=BotResponse, status_code=201)
async def create_bot(
    body: CreateBotRequest,
    principal: Principal = Depends(require_role(UserRole.ADMIN)),
    service: BotService = Depends(_get_bot_service),
    deps: AgentDependencies = Depends(get_deps),
):
    """Create a new bot. Slug must be unique per tenant."""
    tenant_id = principal.tenant_id
    await _enforce_branding_plan_gate(body.widget_config, deps, tenant_id)
    count = await service.count_for_tenant(tenant_id)
    if count >= MAX_BOTS_PER_TENANT:
        raise HTTPException(
            status_code=409,
            detail=f"Bot limit reached ({MAX_BOTS_PER_TENANT}). Delete one first.",
        )
    try:
        bot = await service.create(tenant_id=tenant_id, body=body)
    except BotSlugTakenError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return BotResponse(**bot)


@router.get("", response_model=BotListResponse)
async def list_bots(
    principal: Principal = Depends(require_role(UserRole.VIEWER)),
    service: BotService = Depends(_get_bot_service),
):
    """List all bots for the authenticated tenant."""
    bots = await service.list_for_tenant(principal.tenant_id)
    return BotListResponse(bots=[BotResponse(**b) for b in bots])


@router.get("/{bot_id}", response_model=BotResponse)
async def get_bot(
    bot_id: str,
    principal: Principal = Depends(require_role(UserRole.VIEWER)),
    service: BotService = Depends(_get_bot_service),
):
    """Fetch a single bot. 404 for cross-tenant ids."""
    bot = await service.get(bot_id=bot_id, tenant_id=principal.tenant_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="Bot not found")
    return BotResponse(**bot)


@router.put("/{bot_id}", response_model=BotResponse)
async def update_bot(
    bot_id: str,
    body: UpdateBotRequest,
    principal: Principal = Depends(require_role(UserRole.ADMIN)),
    service: BotService = Depends(_get_bot_service),
    deps: AgentDependencies = Depends(get_deps),
):
    """Partially update a bot. Slug is immutable."""
    await _enforce_branding_plan_gate(body.widget_config, deps, principal.tenant_id)
    bot = await service.update(bot_id=bot_id, tenant_id=principal.tenant_id, body=body)
    if bot is None:
        raise HTTPException(status_code=404, detail="Bot not found")
    return BotResponse(**bot)


@router.delete("/{bot_id}", response_model=MessageResponse)
async def delete_bot(
    bot_id: str,
    principal: Principal = Depends(require_role(UserRole.ADMIN)),
    service: BotService = Depends(_get_bot_service),
):
    """Permanently delete a bot."""
    deleted = await service.delete(bot_id=bot_id, tenant_id=principal.tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Bot not found")
    return MessageResponse(message="Bot deleted")


@router.get("/public/{bot_id}", response_model=PublicBotResponse)
async def get_public_bot(
    bot_id: str,
    service: BotService = Depends(_get_bot_service),
):
    """Public bot config for the widget bootstrap.

    Returns 404 unless the bot exists AND is marked public. Never exposes
    system_prompt, document_filter, or tenant_id. Anonymous access — the
    chat endpoint still requires an API key.
    """
    bot = await service.get_public(bot_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="Bot not found")
    return PublicBotResponse(**bot)
