"""Bot configuration endpoints.

CRUD requires a JWT (dashboard sessions only). A separate public endpoint
exposes a non-secret subset of a bot for widget embedding.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from src.core.dependencies import AgentDependencies
from src.core.deps import get_deps
from src.core.tenant import get_tenant_id_from_jwt
from src.models.api import MessageResponse
from src.models.bot import (
    BotListResponse,
    BotResponse,
    CreateBotRequest,
    PublicBotResponse,
    UpdateBotRequest,
)
from src.services.bot import BotService, BotSlugTakenError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/bots", tags=["bots"])

# Bot count cap per tenant. Plan-based limits live in the billing layer; this
# is a hard ceiling to bound the slug index regardless of plan.
MAX_BOTS_PER_TENANT = 50


def _get_bot_service(deps: AgentDependencies = Depends(get_deps)) -> BotService:
    return BotService(bots_collection=deps.bots_collection)


@router.post("", response_model=BotResponse, status_code=201)
async def create_bot(
    body: CreateBotRequest,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    service: BotService = Depends(_get_bot_service),
):
    """Create a new bot. Slug must be unique per tenant."""
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
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    service: BotService = Depends(_get_bot_service),
):
    """List all bots for the authenticated tenant."""
    bots = await service.list_for_tenant(tenant_id)
    return BotListResponse(bots=[BotResponse(**b) for b in bots])


@router.get("/{bot_id}", response_model=BotResponse)
async def get_bot(
    bot_id: str,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    service: BotService = Depends(_get_bot_service),
):
    """Fetch a single bot. 404 for cross-tenant ids."""
    bot = await service.get(bot_id=bot_id, tenant_id=tenant_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="Bot not found")
    return BotResponse(**bot)


@router.put("/{bot_id}", response_model=BotResponse)
async def update_bot(
    bot_id: str,
    body: UpdateBotRequest,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    service: BotService = Depends(_get_bot_service),
):
    """Partially update a bot. Slug is immutable."""
    bot = await service.update(bot_id=bot_id, tenant_id=tenant_id, body=body)
    if bot is None:
        raise HTTPException(status_code=404, detail="Bot not found")
    return BotResponse(**bot)


@router.delete("/{bot_id}", response_model=MessageResponse)
async def delete_bot(
    bot_id: str,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    service: BotService = Depends(_get_bot_service),
):
    """Permanently delete a bot."""
    deleted = await service.delete(bot_id=bot_id, tenant_id=tenant_id)
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
