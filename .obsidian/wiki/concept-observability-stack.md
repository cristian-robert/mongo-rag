---
title: "Observability stack: structured JSON logs, Sentry, request IDs"
type: concept
tags: [concept, observability, logging, sentry, fastapi]
sources:
  - "apps/api/src/core/observability.py"
  - "apps/api/src/core/request_logging.py"
  - "apps/api/src/routers/health.py"
  - "PR #57"
related:
  - "[[concept-principal-tenant-isolation]]"
created: 2026-04-30
updated: 2026-04-30
status: compiled
---

## Overview

Stdlib `logging` with a custom JSON formatter (NOT structlog), context vars carrying `request_id / tenant_id / user_id` into every log line, automatic redaction of secret-shaped values, an `x-request-id` middleware, and Sentry integration with PII disabled and a before-send redaction hook.

## Content

### JSON formatter — `core/observability.py`

Single-line JSON per record:

```json
{"ts":"2026-04-30T17:21:03.482Z","level":"INFO","logger":"src.routers.chat",
 "service":"mongorag-api","message":"request_complete",
 "request_id":"...","tenant_id":"...","user_id":"...",
 "method":"POST","path":"/api/v1/chat","status":200,"duration_ms":421}
```

- `ts` is ISO 8601 UTC
- `service` is `"mongorag-api"` (constant)
- ContextVars (`request_id`, `tenant_id`, `user_id`) are read on each emit and embedded in every record without per-call boilerplate
- Exceptions add `exc_type`, `exc_message`, and `stack` (server-only — never sent to clients via the sanitizing exception handlers)

### Automatic redaction

Field names matching `(?i)(password|token|api.?key|bearer|secret|...)` are redacted by name. Values matching well-known credential shapes (e.g. `sk_live_*` for Stripe, `Bearer *` for JWT-shaped strings) are redacted regardless of field name. The redaction runs on all extras passed via `logger.info("...", extra={...})`.

### Request ID middleware — `core/request_logging.py`

- Reads `x-request-id` from the inbound request, OR generates a UUID hex if absent
- **Validates** the inbound value (rejects non-hex / overly long inputs) to prevent log-injection attacks
- Stores in the `request_id` ContextVar so downstream loggers see it
- Logs `request_complete` for every request (skipping `/health` and `/ready` to avoid log spam)
- Sanitizes exception responses: never returns stack traces, file paths, or internal exception types to clients

### Sentry — `init_sentry()`

- **No-op if `SENTRY_DSN` is unset OR the SDK isn't installed** — graceful degradation
- Integrations: `FastApiIntegration`, `StarletteIntegration`
- Sample rates configurable via `SENTRY_TRACES_SAMPLE_RATE`, `SENTRY_PROFILES_SAMPLE_RATE` (defaults 0.0 — opt-in)
- `send_default_pii=False`
- Before-send hook redacts request body, cookies, sensitive headers, and any `extra` fields matching the same patterns the JSON formatter scrubs

### Health vs readiness

`routers/health.py` deliberately separates the two:

| Endpoint | What it checks | Response on failure |
|---|---|---|
| `GET /health` | MongoDB ping | 503 if `ConnectionFailure` / `ServerSelectionTimeoutError`. **Does NOT check Postgres or embedding API.** |
| `GET /ready` | MongoDB ping + embedding client configured | 503 with per-component breakdown |

Liveness (`/health`) is the kill-the-pod signal; readiness (`/ready`) is the take-out-of-load-balancer signal. Don't conflate them.

## Key Takeaways

- Stdlib logging + custom JSON formatter; no structlog dependency.
- ContextVars carry `request_id / tenant_id / user_id` into every log emission with zero per-call boilerplate.
- Redaction runs by field-name pattern AND by value shape (catches secrets even when devs mis-name fields).
- Inbound `x-request-id` is validated to prevent log injection — don't trust the header verbatim.
- Sentry has PII off by default; before-send hook re-applies the same redaction the formatter uses.
- `/health` and `/ready` check different things on purpose — wire them to different probes.

## See Also

- [[concept-principal-tenant-isolation]] — the same `tenant_id` ContextVar makes log lines tenant-scoped
