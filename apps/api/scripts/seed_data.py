"""
Seed MongoDB with sample data for local development.

Usage:
    cd apps/api
    uv run python -m scripts.seed_data
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timezone

from pymongo import AsyncMongoClient
from pymongo.errors import ConnectionFailure

from src.core.settings import load_settings
from src.models.document import ChunkModel

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

SEED_TENANT_ID = "tenant_seed_001"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


SEED_TENANT = {
    "tenant_id": SEED_TENANT_ID,
    "name": "Acme Corp",
    "slug": "acme-corp",
    "plan": "free",
    "settings": {
        "max_documents": 10,
        "max_chunks": 1000,
        "max_queries_per_day": 100,
        "custom_system_prompt": None,
        "allowed_origins": ["http://localhost:3100"],
    },
    "created_at": _now(),
    "updated_at": _now(),
}

SEED_USER = {
    "tenant_id": SEED_TENANT_ID,
    "email": "admin@acme.dev",
    "hashed_password": _hash("dev-password-do-not-use"),
    "name": "Dev Admin",
    "role": "owner",
    "is_active": True,
    "created_at": _now(),
    "updated_at": _now(),
}

SEED_API_KEY_RAW = "mr_dev_seed_key_0123456789abcdef"
SEED_API_KEY = {
    "tenant_id": SEED_TENANT_ID,
    "key_hash": _hash(SEED_API_KEY_RAW),
    "key_prefix": SEED_API_KEY_RAW[:8],
    "name": "Development Key",
    "permissions": ["chat", "search"],
    "is_revoked": False,
    "last_used_at": None,
    "created_at": _now(),
}

SEED_DOCUMENT = {
    "tenant_id": SEED_TENANT_ID,
    "title": "Getting Started with MongoRAG",
    "source": "seed://getting-started.md",
    "content": (
        "# Getting Started with MongoRAG\n\n"
        "MongoRAG is a multi-tenant AI chatbot SaaS powered by RAG.\n\n"
        "## Features\n\n"
        "- Upload documents and get AI-powered answers\n"
        "- Embeddable chat widget for any website\n"
        "- Hybrid search combining semantic and text search\n"
    ),
    "content_hash": _hash(
        "# Getting Started with MongoRAG\n\n"
        "MongoRAG is a multi-tenant AI chatbot SaaS powered by RAG.\n\n"
        "## Features\n\n"
        "- Upload documents and get AI-powered answers\n"
        "- Embeddable chat widget for any website\n"
        "- Hybrid search combining semantic and text search\n"
    ),
    "version": 1,
    "etag_or_commit": None,
    "metadata": {"seeded": True},
    "created_at": _now(),
    "updated_at": _now(),
}

# Chunks use zero-vectors since we can't call the embedding API in a seed script
_CHUNK_0_CONTENT = (
    "MongoRAG is a multi-tenant AI chatbot SaaS powered by RAG. "
    "Customers sign up, upload documents, and get an embeddable chat widget."
)
_CHUNK_1_CONTENT = (
    "Features include uploading documents for AI-powered answers, "
    "an embeddable chat widget for any website, and hybrid search "
    "combining semantic and text search."
)
_SEED_SOURCE = "seed://getting-started.md"

SEED_CHUNKS = [
    {
        "tenant_id": SEED_TENANT_ID,
        "document_id": "will-be-set",
        "chunk_id": ChunkModel.generate_chunk_id(_SEED_SOURCE, 1, 0, _CHUNK_0_CONTENT),
        "content": _CHUNK_0_CONTENT,
        "embedding": [0.0] * 1536,
        "chunk_index": 0,
        "heading_path": ["Getting Started with MongoRAG"],
        "content_type": "text",
        "lang": "en",
        "embedding_model": "text-embedding-3-small",
        "token_count": 30,
        "metadata": {"seeded": True},
        "created_at": _now(),
    },
    {
        "tenant_id": SEED_TENANT_ID,
        "document_id": "will-be-set",
        "chunk_id": ChunkModel.generate_chunk_id(_SEED_SOURCE, 1, 1, _CHUNK_1_CONTENT),
        "content": _CHUNK_1_CONTENT,
        "embedding": [0.0] * 1536,
        "chunk_index": 1,
        "heading_path": ["Getting Started with MongoRAG", "Features"],
        "content_type": "text",
        "lang": "en",
        "embedding_model": "text-embedding-3-small",
        "token_count": 35,
        "metadata": {"seeded": True},
        "created_at": _now(),
    },
]

SEED_SUBSCRIPTION = {
    "tenant_id": SEED_TENANT_ID,
    "stripe_customer_id": "cus_seed_dev_000",
    "stripe_subscription_id": None,
    "plan": "free",
    "status": "active",
    "current_period_start": None,
    "current_period_end": None,
    "created_at": _now(),
    "updated_at": _now(),
}

SEED_CONVERSATION = {
    "tenant_id": SEED_TENANT_ID,
    "session_id": "seed-session-001",
    "messages": [
        {
            "role": "user",
            "content": "What is MongoRAG?",
            "sources": [],
            "timestamp": _now(),
        },
        {
            "role": "assistant",
            "content": "MongoRAG is a multi-tenant AI chatbot SaaS powered by RAG.",
            "sources": ["seed://getting-started.md"],
            "timestamp": _now(),
        },
    ],
    "metadata": {"seeded": True},
    "created_at": _now(),
    "updated_at": _now(),
}


async def seed() -> None:
    """Insert seed data into MongoDB."""
    settings = load_settings()
    client = AsyncMongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)

    try:
        try:
            await client.admin.command("ping")
            logger.info("Connected to MongoDB Atlas")
        except ConnectionFailure as e:
            logger.error("Failed to connect: %s", e)
            return

        db = client[settings.mongodb_database]

        # Clean existing seed data
        for coll_name in [
            settings.mongodb_collection_tenants,
            settings.mongodb_collection_users,
            settings.mongodb_collection_api_keys,
            settings.mongodb_collection_documents,
            settings.mongodb_collection_chunks,
            settings.mongodb_collection_subscriptions,
            settings.mongodb_collection_conversations,
        ]:
            result = await db[coll_name].delete_many({"tenant_id": SEED_TENANT_ID})
            if result.deleted_count > 0:
                logger.info(
                    "  Cleaned %d docs from %s",
                    result.deleted_count,
                    coll_name,
                )

        # Insert seed data
        await db[settings.mongodb_collection_tenants].insert_one(SEED_TENANT)
        logger.info("  Seeded tenant: %s", SEED_TENANT["name"])

        await db[settings.mongodb_collection_users].insert_one(SEED_USER)
        logger.info("  Seeded user: %s", SEED_USER["email"])

        await db[settings.mongodb_collection_api_keys].insert_one(SEED_API_KEY)
        logger.info("  Seeded API key: %s...", SEED_API_KEY["key_prefix"])

        doc_result = await db[settings.mongodb_collection_documents].insert_one(SEED_DOCUMENT)
        doc_id = str(doc_result.inserted_id)
        logger.info("  Seeded document: %s (id=%s)", SEED_DOCUMENT["title"], doc_id)

        for chunk in SEED_CHUNKS:
            chunk["document_id"] = doc_id
        await db[settings.mongodb_collection_chunks].insert_many(SEED_CHUNKS)
        logger.info("  Seeded %d chunks", len(SEED_CHUNKS))

        await db[settings.mongodb_collection_subscriptions].insert_one(SEED_SUBSCRIPTION)
        logger.info("  Seeded subscription")

        await db[settings.mongodb_collection_conversations].insert_one(SEED_CONVERSATION)
        logger.info("  Seeded conversation")

        logger.info("Seed complete!")
        logger.info("  Dev API key prefix: %s...", SEED_API_KEY["key_prefix"])
    finally:
        await client.close()


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
