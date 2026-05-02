"""Postgres-backed API key generation, validation, and management (#42).

Schema lives in `supabase/migrations/20260429190107_init_tenancy.sql`:
``public.api_keys (id, tenant_id, created_by, name, prefix, key_hash,
                   last_used_at, revoked_at, created_at)``

Lookup strategy
---------------
1. Filter the candidate set with the indexed ``prefix`` column. The prefix is
   the first 8 characters of the body (excluding the human-readable ``mrag_``
   prefix), which is **not** secret.
2. For every active candidate (``revoked_at IS NULL``), do a ``bcrypt.checkpw``
   against ``key_hash`` in **constant time per candidate**. We always loop the
   full set so a successful match doesn't return faster than a miss.
3. Fire-and-forget update of ``last_used_at`` on success — never blocks the
   request path; failures are logged only.

The raw key is **never** logged. Only the prefix is — it's already public-ish
because the dashboard surfaces it.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import asyncpg
import bcrypt

logger = logging.getLogger(__name__)

# Human-readable wrapper. The body that follows is the secret — its first 8
# chars become `prefix` for indexed lookup.
KEY_PREFIX = "mrag_"
PREFIX_LEN = 8
BCRYPT_ROUNDS = 12  # security.md mandates >= 12


@dataclass(frozen=True)
class GeneratedKey:
    raw_key: str
    prefix: str
    key_hash: str  # bcrypt hash, ascii


@dataclass(frozen=True)
class APIKeyPrincipal:
    """The authenticated identity behind an API key."""

    key_id: str
    tenant_id: str


def _generate_secret() -> str:
    """48 chars (~288 bits) of url-safe entropy, no padding, no underscores."""
    return secrets.token_urlsafe(36).rstrip("=")


def generate_key() -> GeneratedKey:
    """Mint a new API key.

    Returns the raw key (shown once to the user), the indexed prefix, and the
    bcrypt hash to persist. The raw key is never persisted anywhere.
    """
    body = _generate_secret()
    prefix = body[:PREFIX_LEN]
    raw_key = f"{KEY_PREFIX}{body}"
    key_hash = bcrypt.hashpw(raw_key.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS))
    return GeneratedKey(raw_key=raw_key, prefix=prefix, key_hash=key_hash.decode("ascii"))


def _extract_prefix(raw_key: str) -> Optional[str]:
    """Pull the prefix used for indexed lookup, or None if shape is wrong.

    We deliberately don't reveal *why* a key fails — callers map all failures
    to a single 401 to stay timing-uniform.
    """
    if not raw_key.startswith(KEY_PREFIX):
        return None
    body = raw_key[len(KEY_PREFIX) :]
    if len(body) < PREFIX_LEN:
        return None
    return body[:PREFIX_LEN]


async def verify_key(pool: asyncpg.Pool, raw_key: str) -> Optional[APIKeyPrincipal]:
    """Resolve a raw API key to a tenant_id, or None if invalid/revoked.

    - Looks up active rows by ``prefix`` (uses ``api_keys_prefix_idx``).
    - bcrypt-verifies every candidate to avoid early-exit timing leaks.
    - Schedules a non-blocking ``last_used_at`` update on success.
    """
    prefix = _extract_prefix(raw_key)
    if prefix is None:
        return None

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            select id, tenant_id, key_hash
            from public.api_keys
            where prefix = $1 and revoked_at is null
            """,
            prefix,
        )

    matched: Optional[APIKeyPrincipal] = None
    raw_bytes = raw_key.encode("utf-8")
    for row in rows:
        # Always run bcrypt for every row; never short-circuit. bcrypt.checkpw
        # is itself constant-time over the inputs.
        try:
            ok = bcrypt.checkpw(raw_bytes, row["key_hash"].encode("ascii"))
        except ValueError:
            # Malformed stored hash — treat as miss without leaking why.
            ok = False
        if ok and matched is None:
            matched = APIKeyPrincipal(key_id=str(row["id"]), tenant_id=str(row["tenant_id"]))

    if matched is not None:
        _schedule_last_used_update(pool, matched.key_id)
        logger.info(
            "api_key_validated",
            extra={"key_prefix": prefix, "tenant_id": matched.tenant_id},
        )
    return matched


def _schedule_last_used_update(pool: asyncpg.Pool, key_id: str) -> None:
    """Best-effort, non-blocking last_used_at update."""

    async def _update() -> None:
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    "update public.api_keys set last_used_at = $1 where id = $2",
                    datetime.now(timezone.utc),
                    key_id,
                )
        except Exception:
            logger.exception("api_key_last_used_update_failed", extra={"key_id": key_id})

    try:
        asyncio.get_running_loop().create_task(_update())
    except RuntimeError:
        # No running loop — silently drop. Validation result is unaffected.
        pass


async def create_key(
    pool: asyncpg.Pool,
    tenant_id: str,
    name: str,
    created_by: Optional[str] = None,
) -> dict:
    """Insert a new API key for ``tenant_id``. Returns the raw key once."""
    gen = generate_key()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            insert into public.api_keys (tenant_id, created_by, name, prefix, key_hash)
            values ($1, $2, $3, $4, $5)
            returning id, created_at
            """,
            tenant_id,
            created_by,
            name,
            gen.prefix,
            gen.key_hash,
        )
    logger.info(
        "api_key_created",
        extra={"tenant_id": tenant_id, "key_prefix": gen.prefix, "key_name": name},
    )
    return {
        "id": str(row["id"]),
        "raw_key": gen.raw_key,
        "key_prefix": gen.prefix,
        "name": name,
        "created_at": row["created_at"],
    }


async def list_keys(pool: asyncpg.Pool, tenant_id: str) -> list[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            select id, prefix, name, last_used_at, revoked_at, created_at
            from public.api_keys
            where tenant_id = $1
            order by created_at desc
            limit 200
            """,
            tenant_id,
        )
    return [
        {
            "id": str(r["id"]),
            "key_prefix": r["prefix"],
            "name": r["name"],
            "is_revoked": r["revoked_at"] is not None,
            "last_used_at": r["last_used_at"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


async def revoke_key(pool: asyncpg.Pool, key_id: str, tenant_id: str) -> bool:
    """Soft-delete by setting revoked_at. Tenant-scoped — returns False on miss."""
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            update public.api_keys
            set revoked_at = now()
            where id = $1 and tenant_id = $2 and revoked_at is null
            """,
            key_id,
            tenant_id,
        )
    # asyncpg execute returns "UPDATE n"
    affected = int(result.split()[-1]) if result else 0
    if affected:
        logger.info("api_key_revoked", extra={"key_id": key_id, "tenant_id": tenant_id})
    return bool(affected)
