"""Unit tests for WebhookService — tenant isolation, SSRF, secret generation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

from src.models.webhook import CreateWebhookRequest, UpdateWebhookRequest
from src.services.webhook import WebhookLimitExceeded, WebhookService, WebhookURLInvalid


def _make_collection() -> MagicMock:
    coll = MagicMock()
    coll.count_documents = AsyncMock(return_value=0)
    coll.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
    coll.find = MagicMock()
    coll.find_one = AsyncMock()
    coll.find_one_and_update = AsyncMock()
    coll.delete_one = AsyncMock()
    return coll


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_generates_secret_with_prefix():
    coll = _make_collection()
    service = WebhookService(webhooks_collection=coll)
    body = CreateWebhookRequest(url="https://example.com/h", events=["document.ingested"])

    with patch("src.services.webhook.validate_url", side_effect=lambda u: u):
        response, secret = await service.create(tenant_id="t1", body=body)

    assert secret.startswith("whsec_")
    assert len(secret) > len("whsec_") + 16
    # Response never includes the full secret.
    assert "secret" not in response
    assert response["secret_prefix"] != ""


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_rejects_ssrf_url():
    coll = _make_collection()
    service = WebhookService(webhooks_collection=coll)
    body = CreateWebhookRequest(url="http://169.254.169.254/x", events=["document.ingested"])
    from src.services.ingestion.url_loader import URLValidationError

    with patch(
        "src.services.webhook.validate_url",
        side_effect=URLValidationError("metadata blocked"),
    ):
        with pytest.raises(WebhookURLInvalid):
            await service.create(tenant_id="t1", body=body)
    coll.insert_one.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_enforces_per_tenant_limit():
    coll = _make_collection()
    coll.count_documents = AsyncMock(return_value=25)
    service = WebhookService(webhooks_collection=coll)
    body = CreateWebhookRequest(url="https://example.com/h", events=["document.ingested"])
    with patch("src.services.webhook.validate_url", side_effect=lambda u: u):
        with pytest.raises(WebhookLimitExceeded):
            await service.create(tenant_id="t1", body=body)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_filters_by_tenant_id():
    coll = _make_collection()
    service = WebhookService(webhooks_collection=coll)
    oid = ObjectId()
    await service.get(webhook_id=str(oid), tenant_id="t1")
    coll.find_one.assert_awaited_once_with({"_id": oid, "tenant_id": "t1"})


@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_filters_by_tenant_id():
    coll = _make_collection()
    coll.delete_one = AsyncMock(return_value=MagicMock(deleted_count=0))
    service = WebhookService(webhooks_collection=coll)
    oid = ObjectId()
    deleted = await service.delete(webhook_id=str(oid), tenant_id="t1")
    coll.delete_one.assert_awaited_once_with({"_id": oid, "tenant_id": "t1"})
    assert deleted is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_revalidates_url():
    coll = _make_collection()
    service = WebhookService(webhooks_collection=coll)
    body = UpdateWebhookRequest(url="http://localhost/h")
    from src.services.ingestion.url_loader import URLValidationError

    with patch(
        "src.services.webhook.validate_url",
        side_effect=URLValidationError("loopback blocked"),
    ):
        with pytest.raises(WebhookURLInvalid):
            await service.update(webhook_id=str(ObjectId()), tenant_id="t1", body=body)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invalid_object_id_returns_none():
    coll = _make_collection()
    service = WebhookService(webhooks_collection=coll)
    result = await service.get(webhook_id="not-an-objectid", tenant_id="t1")
    assert result is None
    deleted = await service.delete(webhook_id="not-an-objectid", tenant_id="t1")
    assert deleted is False
