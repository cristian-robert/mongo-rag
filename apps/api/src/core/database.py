"""Database index management."""

import logging

from pymongo.asynchronous.database import AsyncDatabase

from src.core.settings import Settings

logger = logging.getLogger(__name__)


async def ensure_indexes(db: AsyncDatabase, settings: Settings) -> None:
    """Create required indexes on all collections.

    Safe to call on every startup — create_index is idempotent.
    Uses collection names from Settings for consistency with the rest
    of the codebase.

    Args:
        db: The async MongoDB database instance.
        settings: Application settings with collection name config.
    """
    logger.info("ensuring_database_indexes")

    # Users: unique email for global email uniqueness
    await db[settings.mongodb_collection_users].create_index("email", unique=True, background=True)

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
