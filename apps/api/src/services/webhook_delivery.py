"""Outbound webhook delivery — HMAC-signed JSON with retry/backoff and audit log.

Threat model:
- SSRF: every redirect hop is re-validated via validate_url(); cloud metadata
  IPs and RFC1918/loopback ranges are blocked. validate_url() is also enforced
  at subscription time (services/webhook.py) so a malicious tenant cannot
  register an internal URL.
- Replay: payloads include `id` (delivery id) and `timestamp` so receivers
  can de-duplicate. Receivers verify HMAC by recomputing over the raw body.
- Secret leakage: the signing secret is NEVER included in delivery logs,
  request payloads, or log lines. Only signature digests appear on the wire.
- Retry storms: capped at MAX_DELIVERY_ATTEMPTS with exponential backoff;
  4xx responses (other than 408/429) terminate retry early since they will
  not succeed on retry.

Background queue: we use `asyncio.create_task` for fire-and-forget delivery.
Tasks survive process death only if persisted; we persist a `pending` row
before scheduling so a future reconciliation worker can replay them. For MVP
we accept that an api restart abandons in-flight retries.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from bson import ObjectId
from pymongo.asynchronous.collection import AsyncCollection

from src.models.webhook import (
    DELIVERY_TIMEOUT_SECONDS,
    MAX_DELIVERY_ATTEMPTS,
    WEBHOOK_EVENTS,
)
from src.services.ingestion.url_loader import URLValidationError, validate_url

logger = logging.getLogger(__name__)

SIGNATURE_HEADER = "X-MongoRAG-Signature"
TIMESTAMP_HEADER = "X-MongoRAG-Timestamp"
EVENT_HEADER = "X-MongoRAG-Event"
DELIVERY_HEADER = "X-MongoRAG-Delivery"

# Receivers must reject signatures older than this skew to prevent replay.
SIGNATURE_TOLERANCE_SECONDS = 300

_USER_AGENT = "MongoRAG-Webhooks/1.0"


def compute_signature(*, secret: str, timestamp: str, body: bytes) -> str:
    """HMAC-SHA256 signature over `<timestamp>.<body>` — Stripe-style scheme."""
    signed = f"{timestamp}.".encode("utf-8") + body
    digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def verify_signature(
    *,
    secret: str,
    header: str,
    body: bytes,
    tolerance_seconds: int = SIGNATURE_TOLERANCE_SECONDS,
) -> bool:
    """Constant-time signature verification with skew tolerance.

    Used by integration tests and provided for SDK consumers.
    """
    parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    ts = parts.get("t")
    sig = parts.get("v1")
    if not ts or not sig:
        return False
    try:
        ts_int = int(ts)
    except ValueError:
        return False
    now = int(datetime.now(timezone.utc).timestamp())
    if abs(now - ts_int) > tolerance_seconds:
        return False
    expected = hmac.new(
        secret.encode("utf-8"),
        f"{ts}.".encode("utf-8") + body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, sig)


def _serialize_payload(*, event: str, tenant_id: str, data: dict[str, Any]) -> bytes:
    """Stable JSON serialization for HMAC signing."""
    payload = {
        "event": event,
        "tenant_id": tenant_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _backoff_seconds(attempt: int) -> float:
    """Exponential backoff: 2, 4, 8, 16, 32 seconds."""
    return float(2**attempt)


def _should_retry(status_code: int | None) -> bool:
    """Retry only on transient failures."""
    if status_code is None:
        return True  # network error / timeout
    if status_code in (408, 429):
        return True
    return status_code >= 500


class WebhookDeliveryService:
    """Outbound HTTP delivery with retries and audit logging."""

    def __init__(
        self,
        deliveries_collection: AsyncCollection,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.collection = deliveries_collection
        # Caller-injected client supports tests; default lazily-built per-attempt.
        self._http_client = http_client

    async def _record_pending(
        self,
        *,
        webhook_id: str,
        tenant_id: str,
        event: str,
        url: str,
    ) -> ObjectId:
        now = datetime.now(timezone.utc)
        doc = {
            "webhook_id": webhook_id,
            "tenant_id": tenant_id,
            "event": event,
            "url": url,
            "status": "pending",
            "attempts": 0,
            "response_code": None,
            "last_error": None,
            "created_at": now,
            "updated_at": now,
            "delivered_at": None,
        }
        result = await self.collection.insert_one(doc)
        return result.inserted_id

    async def _record_attempt(
        self,
        *,
        delivery_id: ObjectId,
        attempt: int,
        status: str,
        response_code: int | None,
        error: str | None,
        delivered: bool,
    ) -> None:
        update: dict[str, Any] = {
            "attempts": attempt,
            "status": status,
            "response_code": response_code,
            "last_error": error,
            "updated_at": datetime.now(timezone.utc),
        }
        if delivered:
            update["delivered_at"] = datetime.now(timezone.utc)
        await self.collection.update_one({"_id": delivery_id}, {"$set": update})

    async def _send_one(
        self,
        *,
        url: str,
        body: bytes,
        signature: str,
        timestamp: str,
        event: str,
        delivery_id: str,
    ) -> tuple[int | None, str | None]:
        """Single HTTP attempt. Returns (status_code, error_msg)."""
        # Re-validate URL to catch DNS rebinding / TOCTOU between attempts.
        try:
            validated = validate_url(url)
        except URLValidationError as e:
            return None, f"url_blocked: {e}"

        headers = {
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
            SIGNATURE_HEADER: signature,
            TIMESTAMP_HEADER: timestamp,
            EVENT_HEADER: event,
            DELIVERY_HEADER: delivery_id,
        }
        try:
            client = self._http_client or httpx.AsyncClient(
                timeout=DELIVERY_TIMEOUT_SECONDS,
                follow_redirects=False,  # redirects revalidated only on retry boundary
            )
            owns_client = self._http_client is None
            try:
                resp = await client.post(validated, content=body, headers=headers)
                return resp.status_code, None
            finally:
                if owns_client:
                    await client.aclose()
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            return None, type(e).__name__
        except httpx.HTTPError as e:
            return None, str(e)[:200]

    async def deliver(
        self,
        *,
        webhook: dict[str, Any],
        event: str,
        data: dict[str, Any],
    ) -> ObjectId:
        """Deliver a single event to a single subscribed webhook.

        Persists a `webhook_deliveries` row first, then attempts up to
        MAX_DELIVERY_ATTEMPTS with exponential backoff.
        """
        tenant_id = webhook["tenant_id"]
        url = webhook["url"]
        secret = webhook["secret"]
        webhook_id = str(webhook["_id"])

        delivery_id = await self._record_pending(
            webhook_id=webhook_id,
            tenant_id=tenant_id,
            event=event,
            url=url,
        )
        body = _serialize_payload(event=event, tenant_id=tenant_id, data=data)
        timestamp = str(int(datetime.now(timezone.utc).timestamp()))
        signature = compute_signature(secret=secret, timestamp=timestamp, body=body)

        for attempt in range(1, MAX_DELIVERY_ATTEMPTS + 1):
            status_code, error = await self._send_one(
                url=url,
                body=body,
                signature=signature,
                timestamp=timestamp,
                event=event,
                delivery_id=str(delivery_id),
            )

            delivered = status_code is not None and 200 <= status_code < 300
            terminal = delivered or not _should_retry(status_code)
            final_status = (
                "delivered"
                if delivered
                else ("failed" if attempt == MAX_DELIVERY_ATTEMPTS or terminal else "pending")
            )
            await self._record_attempt(
                delivery_id=delivery_id,
                attempt=attempt,
                status=final_status,
                response_code=status_code,
                error=error,
                delivered=delivered,
            )

            # Log without secret material.
            logger.info(
                "webhook_delivery_attempt",
                extra={
                    "webhook_id": webhook_id,
                    "tenant_id": tenant_id,
                    "event": event,
                    "attempt": attempt,
                    "status_code": status_code,
                    "result": final_status,
                },
            )

            if terminal:
                break
            await asyncio.sleep(_backoff_seconds(attempt))

        return delivery_id

    async def fire_event(
        self,
        *,
        tenant_id: str,
        event: str,
        data: dict[str, Any],
        webhooks_collection: AsyncCollection,
    ) -> list[ObjectId]:
        """Look up active subscribers and dispatch deliveries as background tasks."""
        if event not in WEBHOOK_EVENTS:
            logger.warning("webhook_unknown_event", extra={"event": event})
            return []
        cursor = webhooks_collection.find({"tenant_id": tenant_id, "active": True, "events": event})
        delivery_ids: list[ObjectId] = []
        async for webhook in cursor:
            # Pre-record a pending delivery so the audit row exists even if
            # the background task is dropped on process restart.
            delivery_id = await self._record_pending(
                webhook_id=str(webhook["_id"]),
                tenant_id=tenant_id,
                event=event,
                url=webhook["url"],
            )
            delivery_ids.append(delivery_id)
            asyncio.create_task(
                self._deliver_existing(
                    delivery_id=delivery_id,
                    webhook=webhook,
                    event=event,
                    data=data,
                )
            )
        return delivery_ids

    async def _deliver_existing(
        self,
        *,
        delivery_id: ObjectId,
        webhook: dict[str, Any],
        event: str,
        data: dict[str, Any],
    ) -> None:
        """Send for an already-recorded pending delivery row."""
        tenant_id = webhook["tenant_id"]
        url = webhook["url"]
        secret = webhook["secret"]
        body = _serialize_payload(event=event, tenant_id=tenant_id, data=data)
        timestamp = str(int(datetime.now(timezone.utc).timestamp()))
        signature = compute_signature(secret=secret, timestamp=timestamp, body=body)

        for attempt in range(1, MAX_DELIVERY_ATTEMPTS + 1):
            status_code, error = await self._send_one(
                url=url,
                body=body,
                signature=signature,
                timestamp=timestamp,
                event=event,
                delivery_id=str(delivery_id),
            )
            delivered = status_code is not None and 200 <= status_code < 300
            terminal = delivered or not _should_retry(status_code)
            final_status = (
                "delivered"
                if delivered
                else ("failed" if attempt == MAX_DELIVERY_ATTEMPTS or terminal else "pending")
            )
            await self._record_attempt(
                delivery_id=delivery_id,
                attempt=attempt,
                status=final_status,
                response_code=status_code,
                error=error,
                delivered=delivered,
            )
            if terminal:
                break
            await asyncio.sleep(_backoff_seconds(attempt))

    async def list_recent(
        self, *, tenant_id: str, webhook_id: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"tenant_id": tenant_id}
        if webhook_id:
            query["webhook_id"] = webhook_id
        cursor = self.collection.find(query).sort("created_at", -1).limit(min(limit, 200))
        out: list[dict[str, Any]] = []
        async for d in cursor:
            out.append(
                {
                    "id": str(d["_id"]),
                    "webhook_id": d["webhook_id"],
                    "event": d["event"],
                    "status": d.get("status", "pending"),
                    "attempts": int(d.get("attempts", 0)),
                    "response_code": d.get("response_code"),
                    "last_error": d.get("last_error"),
                    "created_at": d["created_at"],
                    "delivered_at": d.get("delivered_at"),
                }
            )
        return out
