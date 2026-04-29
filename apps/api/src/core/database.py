"""Database index management."""

import logging

from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import OperationFailure

from src.core.settings import Settings

logger = logging.getLogger(__name__)

# MongoDB error codes for index spec/option conflicts.
_INDEX_CONFLICT_CODES = {
    85,  # IndexOptionsConflict — same key pattern, different options
    86,  # IndexKeySpecsConflict — same name, different key spec
}


def _normalize_key_pattern(keys) -> list[tuple[str, int]]:
    """Normalize index keys to a list of (field, direction) tuples."""
    if isinstance(keys, str):
        return [(keys, 1)]
    return [(k, v) for k, v in keys]


async def _find_index_name(collection: AsyncCollection, keys) -> str | None:
    """Find the name of an existing index matching the given key pattern."""
    target = _normalize_key_pattern(keys)
    indexes = await collection.index_information()
    for name, info in indexes.items():
        if info.get("key") == target:
            return name
    return None


async def _create_index_safe(collection: AsyncCollection, keys, **kwargs) -> None:
    """Create an index, handling spec conflicts by drop-and-recreate.

    If an index with the same key pattern but different options exists,
    discovers the conflicting index name via index_information(), drops
    it, and recreates with the new options. Handles both code 85
    (IndexOptionsConflict) and 86 (IndexKeySpecsConflict).
    """
    try:
        await collection.create_index(keys, **kwargs)
    except OperationFailure as e:
        if e.code in _INDEX_CONFLICT_CODES:
            logger.warning(
                "index_spec_conflict_recreating",
                extra={"collection": collection.name, "keys": str(keys)},
            )
            idx_name = await _find_index_name(collection, keys)
            if idx_name:
                await collection.drop_index(idx_name)
            await collection.create_index(keys, **kwargs)
        else:
            raise


async def ensure_indexes(db: AsyncDatabase, settings: Settings) -> None:
    """Create required indexes on all collections.

    Safe to call on every startup — create_index is idempotent when
    options match. Handles spec conflicts (e.g. upgrading to unique)
    by dropping and recreating the index.

    Args:
        db: The async MongoDB database instance.
        settings: Application settings with collection name config.
    """
    logger.info("ensuring_database_indexes")

    # Users: unique email for global email uniqueness
    await _create_index_safe(
        db[settings.mongodb_collection_users], "email", unique=True, background=True
    )

    # Documents: tenant-scoped listing
    await db[settings.mongodb_collection_documents].create_index(
        [("tenant_id", 1), ("created_at", -1)], background=True
    )

    # Chunks: tenant-scoped lookups by document
    await db[settings.mongodb_collection_chunks].create_index(
        [("tenant_id", 1), ("document_id", 1)], background=True
    )

    # Conversations: tenant-scoped listing
    await db[settings.mongodb_collection_conversations].create_index(
        [("tenant_id", 1), ("created_at", -1)], background=True
    )
    # Conversations: analytics aggregations filter on tenant_id + updated_at
    await db[settings.mongodb_collection_conversations].create_index(
        [("tenant_id", 1), ("updated_at", -1)], background=True
    )

    # API keys: tenant-scoped listing
    await db[settings.mongodb_collection_api_keys].create_index("tenant_id", background=True)

    # Reset tokens: unique hash lookup
    await db[settings.mongodb_collection_reset_tokens].create_index(
        "token_hash", unique=True, background=True
    )

    # Reset tokens: auto-cleanup after 24 hours
    await db[settings.mongodb_collection_reset_tokens].create_index(
        "expires_at", expireAfterSeconds=86400, background=True
    )

    # WS tickets: unique hash lookup
    await db[settings.mongodb_collection_ws_tickets].create_index(
        "ticket_hash", unique=True, background=True
    )

    # WS tickets: auto-cleanup after 60 seconds (tickets expire in 30s)
    await db[settings.mongodb_collection_ws_tickets].create_index(
        "expires_at", expireAfterSeconds=60, background=True
    )

    # Usage: unique per-tenant per-period record (atomic upsert target)
    await _create_index_safe(
        db[settings.mongodb_collection_usage],
        [("tenant_id", 1), ("period_key", 1)],
        unique=True,
        background=True,
    )

    # Bots: tenant-scoped listing
    await db[settings.mongodb_collection_bots].create_index(
        [("tenant_id", 1), ("created_at", -1)], background=True
    )

    # Bots: unique slug per tenant (enforces conflict detection on create)
    await _create_index_safe(
        db[settings.mongodb_collection_bots],
        [("tenant_id", 1), ("slug", 1)],
        unique=True,
        background=True,
    )

    # Users: tenant-scoped listing (team page)
    await db[settings.mongodb_collection_users].create_index(
        [("tenant_id", 1), ("created_at", 1)], background=True
    )

    # Invitations: unique by token_hash (single-use semantics)
    await _create_index_safe(
        db[settings.mongodb_collection_invitations],
        "token_hash",
        unique=True,
        background=True,
    )

    # Invitations: only one PENDING invite per (tenant, email).
    # Partial index allows revoked / accepted rows to coexist.
    await _create_index_safe(
        db[settings.mongodb_collection_invitations],
        [("tenant_id", 1), ("email", 1)],
        unique=True,
        background=True,
        partialFilterExpression={"accepted_at": None, "revoked_at": None},
        name="invitation_pending_unique",
    )

    # Invitations: tenant-scoped listing
    await db[settings.mongodb_collection_invitations].create_index(
        [("tenant_id", 1), ("created_at", -1)], background=True
    )

    # Invitations: TTL cleanup 30 days after expiry (covers revoked + accepted)
    await db[settings.mongodb_collection_invitations].create_index(
        "expires_at", expireAfterSeconds=86400 * 30, background=True
    )

    # Webhooks: tenant-scoped lookups + active subscribers per event
    await db[settings.mongodb_collection_webhooks].create_index(
        [("tenant_id", 1), ("created_at", -1)], background=True
    )
    await db[settings.mongodb_collection_webhooks].create_index(
        [("tenant_id", 1), ("active", 1), ("events", 1)], background=True
    )

    # Webhook deliveries: tenant-scoped recent listing + per-webhook listing
    await db[settings.mongodb_collection_webhook_deliveries].create_index(
        [("tenant_id", 1), ("created_at", -1)], background=True
    )
    await db[settings.mongodb_collection_webhook_deliveries].create_index(
        [("webhook_id", 1), ("created_at", -1)], background=True
    )
    # Auto-prune delivery audit rows after 30 days to bound the collection.
    await db[settings.mongodb_collection_webhook_deliveries].create_index(
        "created_at", expireAfterSeconds=60 * 60 * 24 * 30, background=True
    )

    logger.info("database_indexes_ensured")
