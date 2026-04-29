"""Webhook subscription and delivery management endpoints.

Dashboard-only (JWT). Tenants subscribe to events for their own tenant_id.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.core.dependencies import AgentDependencies
from src.core.deps import get_deps
from src.core.tenant import get_tenant_id_from_jwt
from src.models.api import MessageResponse
from src.models.webhook import (
    WEBHOOK_EVENTS,
    CreateWebhookRequest,
    CreateWebhookResponse,
    TestFireRequest,
    UpdateWebhookRequest,
    WebhookDeliveryListResponse,
    WebhookDeliveryResponse,
    WebhookListResponse,
    WebhookResponse,
)
from src.services.webhook import (
    WebhookLimitExceeded,
    WebhookService,
    WebhookURLInvalid,
)
from src.services.webhook_delivery import WebhookDeliveryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


def _get_webhook_service(deps: AgentDependencies = Depends(get_deps)) -> WebhookService:
    return WebhookService(webhooks_collection=deps.webhooks_collection)


def _get_delivery_service(
    deps: AgentDependencies = Depends(get_deps),
) -> WebhookDeliveryService:
    return WebhookDeliveryService(deliveries_collection=deps.webhook_deliveries_collection)


@router.get("/events", response_model=list[str])
async def list_event_types(
    _: str = Depends(get_tenant_id_from_jwt),
) -> list[str]:
    """Return the available event types tenants can subscribe to."""
    return list(WEBHOOK_EVENTS)


@router.post("", response_model=CreateWebhookResponse, status_code=201)
async def create_webhook(
    body: CreateWebhookRequest,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    service: WebhookService = Depends(_get_webhook_service),
) -> CreateWebhookResponse:
    try:
        response, secret = await service.create(tenant_id=tenant_id, body=body)
    except WebhookLimitExceeded as e:
        raise HTTPException(status_code=409, detail=str(e))
    except WebhookURLInvalid as e:
        raise HTTPException(status_code=422, detail=str(e))
    return CreateWebhookResponse(secret=secret, **response)


@router.get("", response_model=WebhookListResponse)
async def list_webhooks(
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    service: WebhookService = Depends(_get_webhook_service),
) -> WebhookListResponse:
    items = await service.list_for_tenant(tenant_id)
    return WebhookListResponse(webhooks=[WebhookResponse(**i) for i in items])


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: str,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    service: WebhookService = Depends(_get_webhook_service),
) -> WebhookResponse:
    doc = await service.get_response(webhook_id=webhook_id, tenant_id=tenant_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return WebhookResponse(**doc)


@router.patch("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: str,
    body: UpdateWebhookRequest,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    service: WebhookService = Depends(_get_webhook_service),
) -> WebhookResponse:
    try:
        result = await service.update(webhook_id=webhook_id, tenant_id=tenant_id, body=body)
    except WebhookURLInvalid as e:
        raise HTTPException(status_code=422, detail=str(e))
    if result is None:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return WebhookResponse(**result)


@router.delete("/{webhook_id}", response_model=MessageResponse)
async def delete_webhook(
    webhook_id: str,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    service: WebhookService = Depends(_get_webhook_service),
) -> MessageResponse:
    deleted = await service.delete(webhook_id=webhook_id, tenant_id=tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return MessageResponse(message="Webhook deleted")


@router.post("/{webhook_id}/test", response_model=MessageResponse, status_code=202)
async def test_fire_webhook(
    webhook_id: str,
    body: TestFireRequest,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    service: WebhookService = Depends(_get_webhook_service),
    delivery: WebhookDeliveryService = Depends(_get_delivery_service),
    deps: AgentDependencies = Depends(get_deps),
) -> MessageResponse:
    """Fire a synthetic event payload to a single subscribed webhook."""
    webhook = await service.get(webhook_id=webhook_id, tenant_id=tenant_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    if body.event not in webhook["events"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Webhook is not subscribed to this event",
        )
    sample_data = {"test": True, "message": "This is a sample webhook delivery"}
    await delivery.deliver(webhook=webhook, event=body.event, data=sample_data)
    return MessageResponse(message="Test event delivered")


@router.get(
    "/{webhook_id}/deliveries",
    response_model=WebhookDeliveryListResponse,
)
async def list_webhook_deliveries(
    webhook_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    service: WebhookService = Depends(_get_webhook_service),
    delivery: WebhookDeliveryService = Depends(_get_delivery_service),
) -> WebhookDeliveryListResponse:
    # Existence + tenant ownership check.
    webhook = await service.get(webhook_id=webhook_id, tenant_id=tenant_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    items = await delivery.list_recent(tenant_id=tenant_id, webhook_id=webhook_id, limit=limit)
    return WebhookDeliveryListResponse(deliveries=[WebhookDeliveryResponse(**i) for i in items])
