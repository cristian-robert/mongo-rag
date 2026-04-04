"""Database index management."""

import logging

from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import OperationFailure

from src.core.settings import Settings

logger = logging.getLogger(__name__)

# IndexKeySpecsConflict error code — raised when an index exists with
# the same key pattern but different options (e.g. adding unique=True).
_INDEX_CONFLICT_CODE = 86


async def _create_index_safe(
    collection: AsyncCollection, keys, **kwargs
) -> None:
    """Create an index, handling spec conflicts by drop-and-recreate.

    If an index with the same key pattern but different options exists,
    drops it and recreates with the new options. This handles migrations
    like adding unique=True to an existing index.
    """
    try:
        await collection.create_index(keys, **kwargs)
    except OperationFailure as e:
        if e.code == _INDEX_CONFLICT_CODE:
            # Extract the conflicting index name from the error details
            # and drop it before recreating with new options.
            existing = e.details.get("errmsg", "")
            logger.warning(
                "index_spec_conflict_recreating",
                extra={"collection": collection.name, "keys": str(keys)},
            )
            # Build the auto-generated index name the same way MongoDB does:
            # for "email" → "email_1", for [("a",1),("b",-1)] → "a_1_b_-1"
            if isinstance(keys, str):
                idx_name = f"{keys}_1"
            else:
                parts = [f"{k}_{v}" for k, v in keys]
                idx_name = "_".join(parts)
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

    logger.info("database_indexes_ensured")
