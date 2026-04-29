"""Async Postgres connection pool for Supabase service-role operations.

Used by:
- Stripe webhook handler (#43) — writes `subscriptions` and `stripe_events`
  using the service-role key path (bypasses RLS).
- API key validation (#42) — looks up `public.api_keys` before any user
  session exists; tenant isolation is enforced explicitly in every query.
- Future Postgres-backed identity / billing modules.

This module deliberately keeps the API surface tiny — `get_pool` returns a
lazily-created `asyncpg.Pool`. Callers acquire connections via
`async with pool.acquire() as conn:` and use parameterized queries.

Concurrency note: pool creation is guarded by an asyncio.Lock so that
concurrent first-callers do not race to create two pools.

DSN safety: the DSN itself is never logged; only error class on failure.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import asyncpg

from src.core.settings import Settings

logger = logging.getLogger(__name__)


class PostgresUnavailableError(RuntimeError):
    """Raised when SUPABASE_DB_URL is not configured but a pg call is attempted."""


_pool: Optional[asyncpg.Pool] = None
_pool_lock = asyncio.Lock()


async def get_pool(settings: Settings) -> asyncpg.Pool:
    """Return the process-wide asyncpg pool, creating it on first use.

    Raises PostgresUnavailableError when settings.supabase_db_url is unset — callers
    should map that to an HTTP 503 (don't 500: webhook handlers must not
    leak ambiguous failures).
    """
    global _pool
    if _pool is not None:
        return _pool

    if not settings.supabase_db_url:
        raise PostgresUnavailableError(
            "SUPABASE_DB_URL is not configured — Postgres operations are unavailable"
        )

    async with _pool_lock:
        if _pool is None:
            _pool = await asyncpg.create_pool(
                dsn=settings.supabase_db_url,
                min_size=settings.supabase_db_pool_min,
                max_size=settings.supabase_db_pool_max,
                command_timeout=10.0,
                # statement_cache_size=0 keeps us safe behind PgBouncer transaction
                # mode — Supabase's default pooler doesn't allow prepared statements
                # to span transactions.
                statement_cache_size=0,
            )
            logger.info(
                "postgres_pool_created",
                extra={
                    "min_size": settings.supabase_db_pool_min,
                    "max_size": settings.supabase_db_pool_max,
                },
            )
    return _pool


async def try_get_pool(settings: Settings) -> Optional[asyncpg.Pool]:
    """Best-effort accessor — returns ``None`` when Postgres is unconfigured
    or unreachable.

    Used at app startup (#42) so that an unconfigured Postgres does not take
    the API down; callers (API key validation) fall back to the legacy path.
    """
    try:
        return await get_pool(settings)
    except PostgresUnavailableError:
        logger.info("postgres_pool_unconfigured")
        return None
    except Exception:
        logger.exception("postgres_pool_init_failed")
        return None


async def close_pool() -> None:
    """Close the global pool. Called from app shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("postgres_pool_closed")


async def reset_pool_for_tests() -> None:
    """Test-only helper: drop the cached pool without closing it.

    Used by integration tests that swap settings between cases.
    """
    global _pool
    _pool = None
