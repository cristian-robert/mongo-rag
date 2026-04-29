"""CLI for the migration runner.

Usage::

    uv run python -m src.migrations.cli status
    uv run python -m src.migrations.cli up
    uv run python -m src.migrations.cli up --target 0003
    uv run python -m src.migrations.cli down --steps 1

Connects to MongoDB using ``MONGODB_URI`` from the environment. Refuses to run
when ``MONGORAG_ALLOW_PROD=1`` is not set AND ``MONGODB_URI`` looks like a
production cluster (basic guard — full safety is the operator's responsibility).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from pymongo import AsyncMongoClient
from pymongo.errors import ConnectionFailure

from src.migrations import runner

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("migrations")


def _looks_like_prod(uri: str) -> bool:
    lowered = uri.lower()
    return any(token in lowered for token in ("prod", "production"))


async def _run(args: argparse.Namespace) -> int:
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        print("MONGODB_URI is not set", file=sys.stderr)
        return 2

    if _looks_like_prod(uri) and os.environ.get("MONGORAG_ALLOW_PROD") != "1":
        print(
            "Refusing to run migrations against a production-looking URI. "
            "Set MONGORAG_ALLOW_PROD=1 to override.",
            file=sys.stderr,
        )
        return 3

    db_name = os.environ.get("MONGODB_DATABASE", "mongorag")
    client = AsyncMongoClient(uri, serverSelectionTimeoutMS=5000)
    try:
        try:
            await client.admin.command("ping")
        except ConnectionFailure as e:
            print(f"MongoDB connection failed: {e}", file=sys.stderr)
            return 4

        db = client[db_name]
        if args.command == "status":
            rows = await runner.status(db)
            for row in rows:
                marker = "x" if row["applied"] else " "
                print(f"[{marker}] {row['version']}  {row['name']}")
            pending = [r for r in rows if not r["applied"]]
            print(f"\n{len(rows)} known, {len(pending)} pending")
            return 0

        if args.command == "up":
            applied = await runner.up(db, target=args.target)
            if not applied:
                print("No pending migrations.")
            else:
                print(f"Applied: {', '.join(applied)}")
            return 0

        if args.command == "down":
            reverted = await runner.down(db, steps=args.steps)
            if not reverted:
                print("Nothing to revert.")
            else:
                print(f"Reverted: {', '.join(reverted)}")
            return 0

        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1
    finally:
        await client.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="src.migrations.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show applied/pending migrations")

    up_p = sub.add_parser("up", help="Apply pending migrations")
    up_p.add_argument("--target", help="Apply up to and including this version")

    down_p = sub.add_parser("down", help="Revert the last N migrations")
    down_p.add_argument("--steps", type=int, default=1, help="Number of migrations to revert")

    args = parser.parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
