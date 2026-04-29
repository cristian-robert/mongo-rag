"""Per-API-key / per-tenant request rate limiting.

The limiter uses a fixed-window counter (1-minute bucket). Two
backends are provided:

- ``InMemoryRateLimiter`` — single-process default; thread-safe via
  ``asyncio.Lock``. Suitable for dev and single-replica deployments.
- ``RedisRateLimiter`` — uses ``INCR``/``EXPIRE`` for atomic counters
  shared across replicas. Used when ``settings.redis_url`` is reachable.

We picked fixed windows over a sliding log because the cost of an
unbounded log-of-timestamps per key is unacceptable at SaaS scale and
the boundary effect is bounded (≤2× burst at the minute boundary).
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Protocol

logger = logging.getLogger(__name__)


@dataclass
class RateLimitResult:
    """Outcome of a rate-limit decision."""

    allowed: bool
    limit: int
    remaining: int
    reset_in: int  # seconds until current window resets


class RateLimiter(Protocol):
    """Backend interface for rate limiting."""

    async def check(self, key: str, limit: int, window_seconds: int = 60) -> RateLimitResult: ...


@dataclass
class _Bucket:
    window_start: float
    count: int


@dataclass
class InMemoryRateLimiter:
    """Process-local fixed-window counter rate limiter."""

    _buckets: dict[str, _Bucket] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def check(self, key: str, limit: int, window_seconds: int = 60) -> RateLimitResult:
        if limit <= 0:
            return RateLimitResult(allowed=True, limit=limit, remaining=0, reset_in=window_seconds)

        now = time.monotonic()
        async with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None or (now - bucket.window_start) >= window_seconds:
                bucket = _Bucket(window_start=now, count=0)
                self._buckets[key] = bucket
                # Opportunistic cleanup — drop the oldest 25% of stale keys
                # if the dict is getting large to bound memory.
                if len(self._buckets) > 10_000:
                    cutoff = now - window_seconds
                    stale = [k for k, b in self._buckets.items() if b.window_start < cutoff]
                    for k in stale[: len(stale) // 4 + 1]:
                        self._buckets.pop(k, None)

            bucket.count += 1
            allowed = bucket.count <= limit
            remaining = max(limit - bucket.count, 0)
            reset_in = max(int(window_seconds - (now - bucket.window_start)), 1)

            if not allowed:
                # Roll back the over-the-limit increment so we don't
                # punish subsequent retries beyond the window.
                bucket.count -= 1

            return RateLimitResult(
                allowed=allowed, limit=limit, remaining=remaining, reset_in=reset_in
            )


class RedisRateLimiter:
    """Redis-backed atomic fixed-window counter."""

    def __init__(self, redis_client) -> None:
        self.redis = redis_client

    async def check(self, key: str, limit: int, window_seconds: int = 60) -> RateLimitResult:
        if limit <= 0:
            return RateLimitResult(allowed=True, limit=limit, remaining=0, reset_in=window_seconds)

        # Bucket key includes the window number so it rolls over naturally.
        bucket = int(time.time()) // window_seconds
        redis_key = f"ratelimit:{key}:{bucket}"

        # INCR + EXPIRE is two round-trips but atomic per command; pipeline
        # avoids a race where the key never gets a TTL.
        pipe = self.redis.pipeline()
        pipe.incr(redis_key, 1)
        pipe.expire(redis_key, window_seconds + 5)
        results = await pipe.execute()
        count: int = int(results[0])

        allowed = count <= limit
        remaining = max(limit - count, 0)
        # Reset is at the next bucket boundary.
        now_secs = time.time()
        reset_in = max(int((bucket + 1) * window_seconds - now_secs), 1)

        if not allowed:
            try:
                await self.redis.decr(redis_key, 1)
            except Exception:
                logger.exception("rate_limit_rollback_failed", extra={"key": key})

        return RateLimitResult(allowed=allowed, limit=limit, remaining=remaining, reset_in=reset_in)


_DEFAULT_LIMITER: Optional[RateLimiter] = None


def get_default_limiter() -> RateLimiter:
    """Return a process-wide in-memory limiter."""
    global _DEFAULT_LIMITER
    if _DEFAULT_LIMITER is None:
        _DEFAULT_LIMITER = InMemoryRateLimiter()
    return _DEFAULT_LIMITER


def reset_default_limiter() -> None:
    """Test helper — discard the singleton in-memory limiter."""
    global _DEFAULT_LIMITER
    _DEFAULT_LIMITER = None
