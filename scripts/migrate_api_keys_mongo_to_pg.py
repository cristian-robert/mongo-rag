"""One-shot migration: MongoDB ``api_keys`` → Postgres ``public.api_keys``.

This script does **NOT** run automatically. Operators run it once during
the #42 cut-over.

Strategy
--------
The Mongo records store a ``sha256`` hex of the raw key. The Postgres
schema requires a bcrypt hash, which we cannot derive from sha256 — bcrypt
is one-way too. Therefore we **cannot rotate-in-place** without the raw
keys, and forcing customers to rotate is the only safe outcome.

The script:
  1. Counts active (non-revoked) Mongo keys.
  2. If 0 → exits cleanly; safe to drop the Mongo collection.
  3. Otherwise prints a per-tenant rotation report and exits non-zero.
     Operators then notify customers, mint replacement keys via the
     Postgres-backed ``POST /api/v1/keys`` endpoint, and finally drop
     the Mongo collection.

Usage
-----
    uv run python scripts/migrate_api_keys_mongo_to_pg.py [--drop]

The ``--drop`` flag drops the Mongo ``api_keys`` collection ONLY when no
active keys remain. Always dry-run first.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections import Counter

from src.core.dependencies import AgentDependencies

logger = logging.getLogger(__name__)


async def _run(drop: bool) -> int:
    deps = AgentDependencies()
    await deps.initialize()
    try:
        coll = deps.api_keys_collection
        active_filter = {"is_revoked": {"$ne": True}}
        total = await coll.count_documents({})
        active = await coll.count_documents(active_filter)
        print(f"Mongo api_keys: {total} total, {active} active")

        if active == 0:
            print("No active keys. Safe to drop the Mongo collection.")
            if drop:
                await coll.drop()
                print("Dropped Mongo `api_keys` collection.")
            return 0

        print(
            "Cannot migrate keys in place: stored hash is sha256, target is bcrypt.\n"
            "Customers must rotate. Per-tenant active key counts:"
        )
        per_tenant: Counter[str] = Counter()
        async for doc in coll.find(active_filter, {"tenant_id": 1, "name": 1, "key_prefix": 1}):
            per_tenant[str(doc["tenant_id"])] += 1
        for tenant_id, count in per_tenant.most_common():
            print(f"  tenant={tenant_id} keys={count}")
        return 1
    finally:
        await deps.cleanup()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop the Mongo `api_keys` collection if empty.",
    )
    args = parser.parse_args()
    return asyncio.run(_run(drop=args.drop))


if __name__ == "__main__":
    sys.exit(main())
