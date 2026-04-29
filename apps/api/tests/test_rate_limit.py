"""Tests for the in-memory rate limiter."""

import asyncio

import pytest

from src.services.rate_limit import InMemoryRateLimiter


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rate_limiter_allows_requests_under_limit():
    """A burst smaller than the limit is fully allowed."""
    limiter = InMemoryRateLimiter()

    for _ in range(5):
        result = await limiter.check("key-a", limit=10, window_seconds=60)
        assert result.allowed is True

    final = await limiter.check("key-a", limit=10, window_seconds=60)
    assert final.allowed is True
    assert final.remaining == 4
    assert final.limit == 10


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rate_limiter_blocks_when_limit_reached():
    """The (limit+1)th request in a window is rejected."""
    limiter = InMemoryRateLimiter()

    for i in range(3):
        result = await limiter.check("key-b", limit=3, window_seconds=60)
        assert result.allowed is True, f"request {i + 1}/3 should pass"

    blocked = await limiter.check("key-b", limit=3, window_seconds=60)
    assert blocked.allowed is False
    assert blocked.remaining == 0
    assert blocked.reset_in > 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rate_limiter_separates_keys():
    """Distinct keys have independent buckets."""
    limiter = InMemoryRateLimiter()

    for _ in range(3):
        assert (await limiter.check("key-c", limit=3, window_seconds=60)).allowed
    assert (await limiter.check("key-c", limit=3, window_seconds=60)).allowed is False

    # Different key still has full quota
    assert (await limiter.check("key-d", limit=3, window_seconds=60)).allowed is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rate_limiter_window_reset(monkeypatch):
    """After the window elapses, the counter resets."""
    import src.services.rate_limit as rl

    fake_now = [1000.0]

    def fake_monotonic():
        return fake_now[0]

    monkeypatch.setattr(rl.time, "monotonic", fake_monotonic)
    limiter = InMemoryRateLimiter()

    for _ in range(3):
        assert (await limiter.check("key-e", limit=3, window_seconds=60)).allowed
    assert (await limiter.check("key-e", limit=3, window_seconds=60)).allowed is False

    # Advance time past the window
    fake_now[0] = 1100.0
    assert (await limiter.check("key-e", limit=3, window_seconds=60)).allowed is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rate_limiter_zero_limit_disables():
    """A non-positive limit disables the limiter."""
    limiter = InMemoryRateLimiter()

    for _ in range(100):
        result = await limiter.check("key-f", limit=0, window_seconds=60)
        assert result.allowed is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rate_limiter_concurrent_safe():
    """Concurrent calls never let more than `limit` requests through."""
    limiter = InMemoryRateLimiter()

    async def call() -> bool:
        return (await limiter.check("key-g", limit=5, window_seconds=60)).allowed

    results = await asyncio.gather(*[call() for _ in range(20)])
    allowed_count = sum(1 for r in results if r)
    assert allowed_count == 5
