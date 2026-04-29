"""Webhook subscription service — CRUD over the `webhooks` collection.

Tenant isolation: every read and write filters on tenant_id. The service
never trusts the tenant_id from a request body — callers must pass the
tenant_id derived from the authenticated session.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.asynchronous.collection import AsyncCollection

from src.models.webhook import (
    MAX_WEBHOOKS_PER_TENANT,
    WEBHOOK_EVENTS,
    CreateWebhookRequest,
    UpdateWebhookRequest,
)
from src.services.ingestion.url_loader import URLValidationError, validate_url

logger = logging.getLogger(__name__)

_SECRET_PREFIX = "whsec_"
_SECRET_BYTES = 32


class WebhookLimitExceeded(Exception):  # noqa: N818 — domain exception, not stack-trace surface
    """Raised when a tenant tries to exceed MAX_WEBHOOKS_PER_TENANT."""


class WebhookURLInvalid(Exception):  # noqa: N818 — domain exception, not stack-trace surface
    """Raised when the supplied URL fails SSRF / scheme validation."""


def _generate_secret() -> str:
    """Generate a cryptographically random webhook signing secret."""
    return f"{_SECRET_PREFIX}{secrets.token_urlsafe(_SECRET_BYTES)}"


def _doc_to_response(doc: dict[str, Any]) -> dict[str, Any]:
    """Convert a MongoDB document to a response-shaped dict.

    Strips the secret (only the first 6 chars after the prefix are exposed
    via secret_prefix to help users identify a webhook in their logs).
    """
    secret: str = doc.get("secret", "")
    # secret_prefix = first 6 visible chars after the `whsec_` prefix
    body = secret[len(_SECRET_PREFIX) : len(_SECRET_PREFIX) + 6] if secret else ""
    return {
        "id": str(doc["_id"]),
        "url": doc["url"],
        "events": list(doc.get("events", [])),
        "description": doc.get("description"),
        "active": bool(doc.get("active", True)),
        "secret_prefix": body,
        "created_at": doc["created_at"],
        "updated_at": doc.get("updated_at", doc["created_at"]),
    }


class WebhookService:
    """Manage webhook subscriptions for a tenant."""

    def __init__(self, webhooks_collection: AsyncCollection) -> None:
        self.collection = webhooks_collection

    async def count_for_tenant(self, tenant_id: str) -> int:
        return await self.collection.count_documents({"tenant_id": tenant_id})

    async def create(
        self, *, tenant_id: str, body: CreateWebhookRequest
    ) -> tuple[dict[str, Any], str]:
        """Create a webhook subscription. Returns (response_dict, raw_secret)."""
        try:
            normalized_url = validate_url(body.url)
        except URLValidationError as e:
            raise WebhookURLInvalid(str(e)) from e

        count = await self.count_for_tenant(tenant_id)
        if count >= MAX_WEBHOOKS_PER_TENANT:
            raise WebhookLimitExceeded(f"Webhook limit reached ({MAX_WEBHOOKS_PER_TENANT})")

        secret = _generate_secret()
        now = datetime.now(timezone.utc)
        doc = {
            "tenant_id": tenant_id,
            "url": normalized_url,
            "events": list(body.events),
            "description": body.description,
            "active": body.active,
            "secret": secret,
            "created_at": now,
            "updated_at": now,
        }
        result = await self.collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return _doc_to_response(doc), secret

    async def list_for_tenant(self, tenant_id: str) -> list[dict[str, Any]]:
        cursor = self.collection.find({"tenant_id": tenant_id}).sort("created_at", -1)
        return [_doc_to_response(d) async for d in cursor]

    async def get(self, *, webhook_id: str, tenant_id: str) -> dict[str, Any] | None:
        try:
            oid = ObjectId(webhook_id)
        except InvalidId:
            return None
        doc = await self.collection.find_one({"_id": oid, "tenant_id": tenant_id})
        return doc

    async def get_response(self, *, webhook_id: str, tenant_id: str) -> dict[str, Any] | None:
        doc = await self.get(webhook_id=webhook_id, tenant_id=tenant_id)
        return _doc_to_response(doc) if doc else None

    async def update(
        self, *, webhook_id: str, tenant_id: str, body: UpdateWebhookRequest
    ) -> dict[str, Any] | None:
        try:
            oid = ObjectId(webhook_id)
        except InvalidId:
            return None

        update: dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
        if body.url is not None:
            try:
                update["url"] = validate_url(body.url)
            except URLValidationError as e:
                raise WebhookURLInvalid(str(e)) from e
        if body.events is not None:
            update["events"] = list(body.events)
        if body.description is not None:
            update["description"] = body.description
        if body.active is not None:
            update["active"] = body.active

        result = await self.collection.find_one_and_update(
            {"_id": oid, "tenant_id": tenant_id},
            {"$set": update},
            return_document=True,
        )
        if result is None:
            return None
        return _doc_to_response(result)

    async def delete(self, *, webhook_id: str, tenant_id: str) -> bool:
        try:
            oid = ObjectId(webhook_id)
        except InvalidId:
            return False
        result = await self.collection.delete_one({"_id": oid, "tenant_id": tenant_id})
        return result.deleted_count > 0

    async def list_subscribers(self, *, tenant_id: str, event: str) -> list[dict[str, Any]]:
        """Return active webhooks for a tenant subscribed to an event."""
        if event not in WEBHOOK_EVENTS:
            return []
        cursor = self.collection.find({"tenant_id": tenant_id, "active": True, "events": event})
        return [d async for d in cursor]
