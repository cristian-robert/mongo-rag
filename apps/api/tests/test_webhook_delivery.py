"""Tests for outbound webhook delivery: retries, SSRF, audit log."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from bson import ObjectId

from src.services.webhook_delivery import (
    WebhookDeliveryService,
    _backoff_seconds,
    _should_retry,
    verify_signature,
)


def _make_collection_mock() -> MagicMock:
    """Build an AsyncCollection-like mock that records updates."""
    coll = MagicMock()
    coll.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
    coll.update_one = AsyncMock()
    return coll


@pytest.mark.unit
def test_should_retry_treats_5xx_as_transient():
    assert _should_retry(500) is True
    assert _should_retry(502) is True
    assert _should_retry(429) is True
    assert _should_retry(408) is True
    assert _should_retry(None) is True


@pytest.mark.unit
def test_should_retry_treats_4xx_as_terminal():
    assert _should_retry(400) is False
    assert _should_retry(401) is False
    assert _should_retry(404) is False


@pytest.mark.unit
def test_backoff_is_exponential():
    assert _backoff_seconds(1) == 2.0
    assert _backoff_seconds(2) == 4.0
    assert _backoff_seconds(3) == 8.0
    assert _backoff_seconds(4) == 16.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_deliver_records_pending_then_success():
    """A 200 response on first attempt produces one pending row + one delivered update."""
    collection = _make_collection_mock()

    # httpx.AsyncClient mock that returns 200
    mock_response = MagicMock(status_code=200)
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.aclose = AsyncMock()

    service = WebhookDeliveryService(deliveries_collection=collection, http_client=mock_client)

    webhook = {
        "_id": ObjectId(),
        "tenant_id": "t1",
        "url": "https://example.com/hook",
        "secret": "whsec_test",
    }

    with patch(
        "src.services.webhook_delivery.validate_url",
        side_effect=lambda u: u,
    ):
        await service.deliver(webhook=webhook, event="document.ingested", data={"x": 1})

    # 1 pending insert, 1 update for delivered
    assert collection.insert_one.await_count == 1
    assert collection.update_one.await_count == 1
    update_call = collection.update_one.await_args_list[0]
    assert update_call.args[1]["$set"]["status"] == "delivered"
    assert update_call.args[1]["$set"]["response_code"] == 200


@pytest.mark.unit
@pytest.mark.asyncio
async def test_deliver_terminates_on_4xx_no_retry():
    collection = _make_collection_mock()
    mock_response = MagicMock(status_code=404)
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.aclose = AsyncMock()

    service = WebhookDeliveryService(deliveries_collection=collection, http_client=mock_client)
    webhook = {
        "_id": ObjectId(),
        "tenant_id": "t1",
        "url": "https://example.com/hook",
        "secret": "whsec_test",
    }
    with patch("src.services.webhook_delivery.validate_url", side_effect=lambda u: u):
        await service.deliver(webhook=webhook, event="chat.completed", data={})

    # Only one POST attempt — no retry on 404.
    assert mock_client.post.await_count == 1
    update = collection.update_one.await_args_list[-1]
    assert update.args[1]["$set"]["status"] == "failed"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_deliver_retries_5xx_then_succeeds():
    collection = _make_collection_mock()
    responses = [MagicMock(status_code=503), MagicMock(status_code=200)]
    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=responses)
    mock_client.aclose = AsyncMock()

    service = WebhookDeliveryService(deliveries_collection=collection, http_client=mock_client)
    webhook = {
        "_id": ObjectId(),
        "tenant_id": "t1",
        "url": "https://example.com/hook",
        "secret": "whsec_test",
    }
    with patch("src.services.webhook_delivery.validate_url", side_effect=lambda u: u):
        with patch("asyncio.sleep", new=AsyncMock()):  # speed up
            await service.deliver(webhook=webhook, event="document.ingested", data={})
    assert mock_client.post.await_count == 2
    last = collection.update_one.await_args_list[-1]
    assert last.args[1]["$set"]["status"] == "delivered"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_deliver_blocks_ssrf_url():
    """validate_url raising must be recorded as url_blocked, no HTTP request issued."""
    collection = _make_collection_mock()
    mock_client = MagicMock()
    mock_client.post = AsyncMock()  # should NOT be called
    mock_client.aclose = AsyncMock()

    service = WebhookDeliveryService(deliveries_collection=collection, http_client=mock_client)
    webhook = {
        "_id": ObjectId(),
        "tenant_id": "t1",
        "url": "http://169.254.169.254/latest/meta-data/",
        "secret": "whsec_test",
    }
    from src.services.ingestion.url_loader import URLValidationError

    with patch(
        "src.services.webhook_delivery.validate_url",
        side_effect=URLValidationError("blocked metadata"),
    ):
        with patch("asyncio.sleep", new=AsyncMock()):
            await service.deliver(webhook=webhook, event="document.ingested", data={})

    # No HTTP attempts, but rows recorded.
    assert mock_client.post.await_count == 0
    last = collection.update_one.await_args_list[-1]
    set_doc = last.args[1]["$set"]
    assert set_doc["status"] == "failed"
    assert "url_blocked" in (set_doc.get("last_error") or "")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_deliver_treats_network_error_as_retryable():
    collection = _make_collection_mock()
    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("dns fail"))
    mock_client.aclose = AsyncMock()

    service = WebhookDeliveryService(deliveries_collection=collection, http_client=mock_client)
    webhook = {
        "_id": ObjectId(),
        "tenant_id": "t1",
        "url": "https://example.com/hook",
        "secret": "whsec_test",
    }
    with patch("src.services.webhook_delivery.validate_url", side_effect=lambda u: u):
        with patch("asyncio.sleep", new=AsyncMock()):
            await service.deliver(webhook=webhook, event="document.ingested", data={})

    # All 5 attempts must be made on transient network failure.
    assert mock_client.post.await_count == 5
    last = collection.update_one.await_args_list[-1]
    assert last.args[1]["$set"]["status"] == "failed"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_signature_can_be_verified_by_receiver():
    """Capture the headers we send and verify them as a real receiver would."""
    captured: dict = {}

    async def fake_post(url, content, headers):
        captured["url"] = url
        captured["body"] = content
        captured["headers"] = headers
        return MagicMock(status_code=200)

    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=fake_post)
    mock_client.aclose = AsyncMock()

    collection = _make_collection_mock()
    service = WebhookDeliveryService(deliveries_collection=collection, http_client=mock_client)
    webhook = {
        "_id": ObjectId(),
        "tenant_id": "t1",
        "url": "https://example.com/h",
        "secret": "whsec_realsecret",
    }
    with patch("src.services.webhook_delivery.validate_url", side_effect=lambda u: u):
        await service.deliver(webhook=webhook, event="chat.completed", data={"q": "hi"})

    sig_header = captured["headers"]["X-MongoRAG-Signature"]
    assert verify_signature(secret="whsec_realsecret", header=sig_header, body=captured["body"])
    # Wrong secret must fail verification.
    assert not verify_signature(secret="whsec_wrong", header=sig_header, body=captured["body"])
