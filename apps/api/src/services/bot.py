"""Bot CRUD service. All operations are tenant-scoped at the query layer."""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import DuplicateKeyError

from src.models.bot import CreateBotRequest, UpdateBotRequest

logger = logging.getLogger(__name__)


class BotSlugTakenError(Exception):
    """Raised when a slug is already used by another bot in the same tenant."""


class BotNotFoundError(Exception):
    """Raised when a bot does not exist or belongs to another tenant."""


def _doc_to_response(doc: dict[str, Any]) -> dict[str, Any]:
    """Convert a MongoDB doc to API response shape (id as str, drop _id)."""
    return {
        "id": str(doc["_id"]),
        "tenant_id": doc["tenant_id"],
        "name": doc["name"],
        "slug": doc["slug"],
        "description": doc.get("description"),
        "system_prompt": doc["system_prompt"],
        "welcome_message": doc.get("welcome_message", "Hi! How can I help you today?"),
        "tone": doc.get("tone", "professional"),
        "is_public": doc.get("is_public", False),
        # Stored under model_config_ — surface as model_config for the API.
        "model_config": doc.get("model_config_", {"temperature": 0.2, "max_tokens": 1024}),
        "widget_config": doc.get(
            "widget_config",
            {
                "primary_color": "#0f172a",
                "position": "bottom-right",
                "avatar_url": None,
            },
        ),
        "document_filter": doc.get("document_filter", {"mode": "all", "document_ids": []}),
        "created_at": doc["created_at"],
        "updated_at": doc["updated_at"],
    }


class BotService:
    """Manages bot configuration documents in MongoDB."""

    def __init__(self, bots_collection: AsyncCollection) -> None:
        self._bots = bots_collection

    async def create(self, tenant_id: str, body: CreateBotRequest) -> dict[str, Any]:
        """Create a new bot for a tenant.

        Raises BotSlugTakenError if (tenant_id, slug) already exists.
        """
        now = datetime.now(timezone.utc)
        # Pull through the model_config alias.
        payload = body.model_dump(by_alias=False)
        # rename internal `model_config_` (BaseModel reserved-name workaround)
        # to the storage key `model_config_` to make MongoDB happy and avoid
        # collisions with Pydantic internals on read.
        doc = {
            "tenant_id": tenant_id,
            "name": payload["name"],
            "slug": payload["slug"],
            "description": payload.get("description"),
            "system_prompt": payload["system_prompt"],
            "welcome_message": payload["welcome_message"],
            "tone": payload["tone"],
            "is_public": payload["is_public"],
            "model_config_": payload["model_config_"],
            "widget_config": payload["widget_config"],
            "document_filter": payload["document_filter"],
            "created_at": now,
            "updated_at": now,
        }

        try:
            result = await self._bots.insert_one(doc)
        except DuplicateKeyError as e:
            raise BotSlugTakenError(f"Slug '{payload['slug']}' is already in use") from e

        doc["_id"] = result.inserted_id
        logger.info(
            "bot_created",
            extra={"tenant_id": tenant_id, "bot_id": str(result.inserted_id)},
        )
        return _doc_to_response(doc)

    async def list_for_tenant(self, tenant_id: str) -> list[dict[str, Any]]:
        """Return all bots for a tenant, newest first."""
        cursor = self._bots.find({"tenant_id": tenant_id}).sort("created_at", -1)
        docs = await cursor.to_list(length=200)
        return [_doc_to_response(d) for d in docs]

    async def get(self, bot_id: str, tenant_id: str) -> Optional[dict[str, Any]]:
        """Fetch a single bot scoped to tenant."""
        try:
            oid = ObjectId(bot_id)
        except Exception:
            return None
        doc = await self._bots.find_one({"_id": oid, "tenant_id": tenant_id})
        if doc is None:
            return None
        return _doc_to_response(doc)

    async def update(
        self, bot_id: str, tenant_id: str, body: UpdateBotRequest
    ) -> Optional[dict[str, Any]]:
        """Apply a partial update.

        Returns the updated bot, or None if not found / wrong tenant.
        Slug is intentionally not updatable to keep embed snippets stable.
        """
        try:
            oid = ObjectId(bot_id)
        except Exception:
            return None

        update: dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
        payload = body.model_dump(by_alias=False, exclude_none=True)

        for key in (
            "name",
            "description",
            "system_prompt",
            "welcome_message",
            "tone",
            "is_public",
        ):
            if key in payload:
                update[key] = payload[key]

        if "model_config_" in payload:
            update["model_config_"] = payload["model_config_"]
        if "widget_config" in payload:
            update["widget_config"] = payload["widget_config"]
        if "document_filter" in payload:
            update["document_filter"] = payload["document_filter"]

        doc = await self._bots.find_one_and_update(
            {"_id": oid, "tenant_id": tenant_id},
            {"$set": update},
            return_document=True,
        )
        if doc is None:
            return None
        return _doc_to_response(doc)

    async def delete(self, bot_id: str, tenant_id: str) -> bool:
        """Hard-delete a bot. Returns True if removed, False if not found."""
        try:
            oid = ObjectId(bot_id)
        except Exception:
            return False
        result = await self._bots.delete_one({"_id": oid, "tenant_id": tenant_id})
        if result.deleted_count == 0:
            return False
        logger.info(
            "bot_deleted",
            extra={"tenant_id": tenant_id, "bot_id": bot_id},
        )
        return True

    async def get_public(self, bot_id: str) -> Optional[dict[str, Any]]:
        """Public lookup by id — only returns the bot if it's marked public.

        Used by the embeddable widget to bootstrap appearance without
        requiring a JWT. NEVER returns system_prompt, document_filter, or
        tenant identifiers.
        """
        try:
            oid = ObjectId(bot_id)
        except Exception:
            return None
        doc = await self._bots.find_one({"_id": oid, "is_public": True})
        if doc is None:
            return None
        return {
            "id": str(doc["_id"]),
            "slug": doc["slug"],
            "name": doc["name"],
            "welcome_message": doc.get("welcome_message", "Hi! How can I help you today?"),
            "widget_config": doc.get(
                "widget_config",
                {
                    "primary_color": "#0f172a",
                    "position": "bottom-right",
                    "avatar_url": None,
                },
            ),
        }

    async def count_for_tenant(self, tenant_id: str) -> int:
        """Count bots for a tenant — used to enforce plan limits."""
        return await self._bots.count_documents({"tenant_id": tenant_id})
