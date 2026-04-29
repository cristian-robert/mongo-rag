"""0001 baseline — assert all standard indexes exist.

This migration is idempotent. It calls ``pymongo.create_index`` for every
collection used by MongoRAG. Atlas Vector Search and Atlas Search indexes
are NOT created here — those must be managed via the Atlas UI or Atlas CLI.

Down-migration drops only the indexes this migration created (by name).
"""

from __future__ import annotations

from pymongo import ASCENDING as ASC
from pymongo import DESCENDING as DESC
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import OperationFailure

VERSION = "0001"
NAME = "baseline_indexes"

# (collection, keys, options, name)
_INDEX_SPECS: list[tuple[str, list[tuple[str, int]], dict, str]] = [
    ("chunks", [("tenant_id", ASC), ("document_id", ASC)], {}, "chunks_tenant_doc"),
    (
        "chunks",
        [("tenant_id", ASC), ("chunk_id", ASC)],
        {"unique": True},
        "chunks_tenant_chunkid_uq",
    ),
    ("chunks", [("tenant_id", ASC), ("created_at", DESC)], {}, "chunks_tenant_created"),
    ("chunks", [("chunk_id", ASC)], {}, "chunks_chunkid"),
    ("documents", [("tenant_id", ASC), ("source", ASC)], {}, "documents_tenant_source"),
    ("documents", [("tenant_id", ASC), ("content_hash", ASC)], {}, "documents_tenant_hash"),
    ("documents", [("tenant_id", ASC), ("created_at", DESC)], {}, "documents_tenant_created"),
    ("tenants", [("tenant_id", ASC)], {"unique": True}, "tenants_tenantid_uq"),
    ("tenants", [("slug", ASC)], {"unique": True}, "tenants_slug_uq"),
    ("users", [("email", ASC)], {"unique": True}, "users_email_uq"),
    ("users", [("tenant_id", ASC)], {}, "users_tenant"),
    ("api_keys", [("key_hash", ASC)], {"unique": True}, "api_keys_hash_uq"),
    ("api_keys", [("tenant_id", ASC)], {}, "api_keys_tenant"),
    ("conversations", [("tenant_id", ASC), ("session_id", ASC)], {}, "conv_tenant_session"),
    ("conversations", [("tenant_id", ASC), ("created_at", DESC)], {}, "conv_tenant_created"),
    ("subscriptions", [("tenant_id", ASC)], {"unique": True}, "subs_tenant_uq"),
    ("subscriptions", [("stripe_customer_id", ASC)], {}, "subs_stripe_customer"),
]


async def up(db: AsyncDatabase) -> None:
    for coll, keys, opts, name in _INDEX_SPECS:
        try:
            await db[coll].create_index(keys, name=name, **opts)
        except OperationFailure as e:
            # 85/86 = options/spec conflict — index exists with different opts.
            # Treat as already-applied for idempotency; let humans resolve.
            if e.code not in (85, 86):
                raise


async def down(db: AsyncDatabase) -> None:
    for coll, _keys, _opts, name in _INDEX_SPECS:
        try:
            await db[coll].drop_index(name)
        except OperationFailure as e:
            # 27 = IndexNotFound — already gone, fine.
            if e.code != 27:
                raise
