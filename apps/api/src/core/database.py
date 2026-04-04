"""Database index management."""

import logging

from pymongo.asynchronous.database import AsyncDatabase

logger = logging.getLogger(__name__)


async def ensure_indexes(db: AsyncDatabase) -> None:
    """Create required indexes on all collections.

    Safe to call on every startup — create_index is idempotent.

    Args:
        db: The async MongoDB database instance.
    """
    logger.info("ensuring_database_indexes")

    # Users: unique email for global email uniqueness
    await db["users"].create_index("email", unique=True, background=True)

    # Documents: tenant-scoped listing
    await db["documents"].create_index([("tenant_id", 1), ("created_at", -1)], background=True)

    # Chunks: tenant-scoped lookups by document
    await db["chunks"].create_index([("tenant_id", 1), ("document_id", 1)], background=True)

    # Conversations: tenant-scoped listing
    await db["conversations"].create_index([("tenant_id", 1), ("created_at", -1)], background=True)

    # API keys: tenant-scoped listing
    await db["api_keys"].create_index("tenant_id", background=True)

    # Reset tokens: hash lookup
    await db["password_reset_tokens"].create_index("token_hash", background=True)

    # Reset tokens: auto-cleanup after 24 hours
    await db["password_reset_tokens"].create_index(
        "expires_at", expireAfterSeconds=86400, background=True
    )

    logger.info("database_indexes_ensured")
