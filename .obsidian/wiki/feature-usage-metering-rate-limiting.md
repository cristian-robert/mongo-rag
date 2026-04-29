---
title: "Feature: Usage Metering and Rate Limiting"
type: feature
tags: [feature, billing, security, mongodb]
sources:
  - "GitHub issue #11"
  - "git log: feat/usage-metering-rate-limit branch"
related:
  - "[[feature-stripe-billing]]"
  - "[[feature-api-key-management]]"
  - "[[multi-tenancy-tenant-isolation]]"
created: 2026-04-29
updated: 2026-04-29
status: active
---

## Summary

Plan-tier usage metering and rate limiting for the MongoRAG SaaS. Tracks per-tenant, per-period counters (queries, documents, chunks, embedding tokens) in MongoDB and enforces both per-minute request rate limits and monthly query quotas. Returns `429 Too Many Requests` with a `Retry-After` header when limits are hit. Document caps are enforced before ingest accepts the upload.

## GitHub Issues

| Issue | Title | Status |
|-------|-------|--------|
| #11 | Implement usage metering and rate limiting | shipped |

## Key Decisions

- **Plan limits live in code** (`src/models/usage.py::PlanLimits.for_plan`) rather than a Stripe-driven config table — design simplicity, easy to test. Stripe webhooks (#10) update only the active `plan` on the `subscriptions` collection; this module reads that and resolves limits.
- **Reservation pattern for query quota** — atomically `$inc queries_count` and roll back if the post-increment value crosses the limit. Eliminates the read-then-write race. Bounded over-counting is acceptable because the rollback runs synchronously before the request is processed.
- **Fixed-window rate limiting** rather than sliding-log — O(1) memory per key. Boundary spike (≤2× burst at minute boundary) is acceptable at this stage.
- **In-memory limiter as default**, Redis backend for multi-replica deployments — Redis already wired for Celery, so the cost of a multi-process limiter is trivial when needed.
- **Cancelled / past_due → FREE limits** — non-active subscriptions cannot keep using paid tier limits.
- **Usage endpoint is JWT-only** — API keys must not introspect usage.

## Implementation Notes

- New collection `usage` — `{tenant_id, period_key (YYYY-MM), period_start, period_end, queries_count, documents_count, chunks_count, embedding_tokens_count, created_at, updated_at}` with a unique compound index on `(tenant_id, period_key)`. Period rollover is implicit — the first increment in a new month upserts a fresh period record.
- `UsageService` (`src/services/usage.py`) — atomic increment, plan resolution, quota checks. `current_period_key()` and `period_bounds()` are pure helpers used by both runtime and tests.
- `RateLimiter` (`src/services/rate_limit.py`) — `InMemoryRateLimiter` (default singleton) + `RedisRateLimiter` (atomic via pipeline). Concurrent-safe via `asyncio.Lock` for the in-memory variant.
- FastAPI dependencies (`src/core/rate_limit_dep.py`) — `enforce_rate_limit` for ingest and other write paths, `enforce_query_quota` for `/chat`. Both raise 429 with `Retry-After` and `X-RateLimit-*` / `X-Quota-*` headers.
- `GET /api/v1/usage` (`src/routers/usage.py`) — returns counters + plan limits + percent + warning/blocked flags. Document/chunk gauges read live counts from collections so they are correct even if hooks miss.
- Per-API-key vs per-tenant rate-limit key — derived from the `Authorization` header. Hashed (SHA-256, 32-char prefix) for API keys; tenant_id for JWT sessions.
- Plan tiers (queries / documents / chunks / requests-per-minute / embedding tokens):
  - **Free** — 100 / 10 / 1k / 60 / 50k
  - **Starter** — 2k / 100 / 20k / 120 / 500k
  - **Pro** — 10k / 1k / 200k / 300 / 5M
  - **Enterprise** — 1M / 100k / 20M / 1k / 500M

## Endpoints

- `GET /api/v1/usage` — JWT-only; returns the period's counters, limits, and warning/blocked flags.
- `POST /api/v1/chat` — now wrapped by `enforce_query_quota` → returns 429 when per-minute or monthly quota exceeded.
- `POST /api/v1/documents/ingest` — now wrapped by `enforce_rate_limit` and pre-checks `documents_max` before accepting the upload.

## Key Takeaways

- Quota reservation must roll back the over-the-limit increment — otherwise the counter drifts past the limit on retries.
- The rate limiter must be reset between tests — the singleton holds bucket state across requests in the same process.
- Document/chunk counts are gauges (sourced from live counts), not increment-only counters — chunk deletion would otherwise leave stale numbers.
- API keys must never read usage data — leakage of plan limits could aid abuse planning.

## See Also

- `[[feature-stripe-billing]]` — plan tier comes from the Stripe-managed subscription
- `[[feature-api-key-management]]` — API key hash drives the per-key rate limit bucket
- `[[multi-tenancy-tenant-isolation]]` — every counter is scoped by `tenant_id` derived from the auth principal
