"""
Create MongoDB indexes for all collections.

Usage:
    cd apps/api
    uv run python -m scripts.setup_indexes

NOTE: Atlas Vector Search and Atlas Search indexes can be created programmatically
via createSearchIndexes / Atlas Admin API / Atlas CLI, but are easier to manage
through the Atlas UI. This script handles all standard compound and single-field
indexes only.

Atlas UI index definitions are documented at the bottom of this file.
"""

import asyncio
import logging

from pymongo import ASCENDING as ASC
from pymongo import DESCENDING as DESC
from pymongo import AsyncMongoClient
from pymongo.errors import ConnectionFailure, OperationFailure

from src.core.settings import load_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def create_indexes() -> None:
    """Create all required MongoDB indexes."""
    settings = load_settings()
    client = AsyncMongoClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=5000,
    )

    try:
        try:
            await client.admin.command("ping")
            logger.info("Connected to MongoDB Atlas")
        except ConnectionFailure as e:
            logger.error("Failed to connect to MongoDB: %s", e)
            return

        db = client[settings.mongodb_database]

        # -- chunks collection --
        c = db[settings.mongodb_collection_chunks]
        await _create_index(c, "chunks", [("tenant_id", ASC), ("document_id", ASC)])
        await _create_index(c, "chunks", [("tenant_id", ASC), ("chunk_id", ASC)], unique=True)
        await _create_index(c, "chunks", [("tenant_id", ASC), ("created_at", DESC)])
        await _create_index(c, "chunks", [("chunk_id", ASC)])

        # -- documents collection --
        d = db[settings.mongodb_collection_documents]
        await _create_index(d, "documents", [("tenant_id", ASC), ("source", ASC)])
        await _create_index(d, "documents", [("tenant_id", ASC), ("content_hash", ASC)])
        await _create_index(d, "documents", [("tenant_id", ASC), ("created_at", DESC)])
        await _create_index(d, "documents", [("tenant_id", ASC), ("version", ASC)])

        # -- tenants collection --
        t = db[settings.mongodb_collection_tenants]
        await _create_index(t, "tenants", [("tenant_id", ASC)], unique=True)
        await _create_index(t, "tenants", [("slug", ASC)], unique=True)

        # -- users collection --
        u = db[settings.mongodb_collection_users]
        await _create_index(u, "users", [("email", ASC)], unique=True)
        await _create_index(u, "users", [("tenant_id", ASC)])

        # -- conversations collection --
        cv = db[settings.mongodb_collection_conversations]
        await _create_index(cv, "conversations", [("tenant_id", ASC), ("session_id", ASC)])
        await _create_index(cv, "conversations", [("tenant_id", ASC), ("created_at", DESC)])

        # -- api_keys collection --
        ak = db[settings.mongodb_collection_api_keys]
        await _create_index(ak, "api_keys", [("key_hash", ASC)], unique=True)
        await _create_index(ak, "api_keys", [("tenant_id", ASC)])
        await _create_index(ak, "api_keys", [("key_prefix", ASC)])

        # -- password_reset_tokens collection --
        rt = db[settings.mongodb_collection_reset_tokens]
        await _create_index(rt, "password_reset_tokens", [("token_hash", ASC)], unique=True)
        await _create_index(rt, "password_reset_tokens", [("user_id", ASC)])

        # -- subscriptions collection --
        s = db[settings.mongodb_collection_subscriptions]
        await _create_index(s, "subscriptions", [("tenant_id", ASC)], unique=True)
        await _create_index(s, "subscriptions", [("stripe_customer_id", ASC)])
        await _create_index(s, "subscriptions", [("stripe_subscription_id", ASC)])

        logger.info("All indexes created successfully")
    finally:
        await client.close()


async def _create_index(
    collection,
    collection_name: str,
    keys: list[tuple[str, int]],
    unique: bool = False,
) -> None:
    """Create a single index with error handling."""
    key_desc = ", ".join(f"{k}:{d}" for k, d in keys)
    try:
        await collection.create_index(keys, unique=unique)
        suffix = " [unique]" if unique else ""
        logger.info("  %s: created index (%s)%s", collection_name, key_desc, suffix)
    except OperationFailure as e:
        if "already exists" in str(e).lower():
            logger.info("  %s: index already exists (%s)", collection_name, key_desc)
        else:
            logger.error("  %s: failed to create index (%s): %s", collection_name, key_desc, e)


def main() -> None:
    asyncio.run(create_indexes())


if __name__ == "__main__":
    main()


# =============================================================================
# ATLAS SEARCH INDEX DEFINITIONS (create via Atlas UI or Atlas CLI)
# =============================================================================
#
# 1. Vector Search Index: "vector_index" on "chunks" collection
#    {
#      "fields": [
#        {
#          "type": "vector",
#          "path": "embedding",
#          "numDimensions": 1536,
#          "similarity": "cosine"
#        },
#        {
#          "type": "filter",
#          "path": "tenant_id"
#        }
#      ]
#    }
#
# 2. Atlas Search Index: "text_index" on "chunks" collection
#    {
#      "mappings": {
#        "dynamic": false,
#        "fields": {
#          "content": {
#            "type": "string",
#            "analyzer": "lucene.standard"
#          },
#          "tenant_id": {
#            "type": "string"
#          }
#        }
#      }
#    }
#
# Atlas Tier Notes:
# - Free (M0): Vector Search supported, 0.5GB storage, 100 ops/sec
# - Flex ($8-30/mo): 5GB, 500 ops/sec, no private endpoints
# - Dedicated M10+ (~$57/mo): Full features, $rankFusion, continuous backups
# =============================================================================
