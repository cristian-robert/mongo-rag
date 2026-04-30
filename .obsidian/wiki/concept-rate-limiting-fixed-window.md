---
title: "Fixed-window rate limiting"
type: concept
tags: [concept, rate-limiting, redis, fastapi]
sources:
  - "apps/api/src/services/rate_limit.py"
  - "apps/api/src/services/usage.py"
  - "PR #49"
related:
  - "[[feature-usage-metering-rate-limiting]]"
created: 2026-04-30
updated: 2026-04-30
status: compiled
---

## Overview

Rate limiting uses a **fixed-window** counter (not token-bucket), implemented as a Protocol with two backends: in-memory (single-replica dev) and Redis (multi-replica production). Plan-tier limits are passed in by callers; the limiter itself is plan-agnostic.

## Content

### Interface

```python
class RateLimiter(Protocol):
    async def check(self, key: str, limit: int, window_seconds: int) -> RateLimitResult: ...
```

`RateLimitResult` exposes whether the request is allowed plus retry-after metadata for `429` responses.

### Implementations

- **`InMemoryRateLimiter`** — process-local dict + `asyncio.Lock`. Suitable for dev / single-replica only.
- **`RedisRateLimiter`** — atomic `INCR` + `EXPIRE` pipelined per check. Survives multi-replica deployments.

Both share the same key format: `ratelimit:{key}:{bucket}` where `bucket = floor(now / window_seconds)`.

### Algorithm

Fixed-window counter with two extra defenses:

- **Burst bound:** at boundary transitions, two adjacent windows can both be near-full, so the worst-case burst is **≤ 2× limit** in a `2 × window_seconds` span. Acceptable for our SLAs; not chosen if strict smoothing is required.
- **Rollback on rejection:** when an `INCR` pushes the counter over `limit`, the limiter decrements it back so a denied request doesn't punish the next caller with a stricter retry-after.

### Plan-tier wiring

The limiter doesn't know about plans. Callers (e.g. `routers/team.py:_enforce_invite_rate_limit`, the chat endpoint, the IP-based auth-rate-limit middleware) compute the plan-appropriate `limit` and `window_seconds` from `services/usage.py:UsageService.get_plan(tenant_id)` and pass them in.

This keeps the limiter reusable: per-tenant API quotas, per-IP auth throttling, and per-tenant invite throttling all use the same primitive with different `(key, limit, window)` triples.

### Usage / quota separation

Rate limiting (`rate_limit.py`) and quota enforcement (`usage.py`) are deliberately separate:

- **Rate limit:** "this caller is sending too fast — back off" (HTTP 429, retry later)
- **Quota:** "this tenant has hit their monthly cap — upgrade required" (HTTP 402 / 403, no retry-after)

`usage.py` uses a reserve-and-rollback pattern over the per-`(tenant_id, period_key)` MongoDB `usage` document for monthly counters: `queries_count`, `documents_count`, `chunks_count`, `embedding_tokens_count`. `period_key = YYYY-MM`.

## Key Takeaways

- Fixed-window, not token-bucket. Burst ≤ 2× over a 2-window span.
- Two backends behind a single Protocol; Redis path is the production default.
- The limiter is plan-agnostic — callers inject `limit` / `window_seconds`.
- Rollback on rejection so denied requests don't worsen the next allowed one's retry-after.
- Rate limiting ≠ quota. Separate concerns; separate primitives; separate HTTP status codes.

## See Also

- [[feature-usage-metering-rate-limiting]] — the higher-level feature that wires plans into limits
