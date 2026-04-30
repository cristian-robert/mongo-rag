---
title: "Feature: Outbound webhooks"
type: feature
tags: [feature, webhooks, integration, hmac]
sources:
  - "apps/api/src/services/webhook.py"
  - "apps/api/src/services/webhook_delivery.py"
  - "apps/api/src/routers/webhooks.py"
  - "PR #67"
related:
  - "[[concept-ssrf-defense-url-ingestion]]"
  - "[[concept-stripe-webhook-idempotency]]"
created: 2026-04-30
updated: 2026-04-30
status: compiled
---

## Overview

Tenants register HTTPS endpoints to receive event notifications (e.g. `document.created`, `bot.updated`). Events are POSTed with an HMAC-SHA256 signature in a Stripe-style header, retried with exponential backoff on transient failures, and recorded for audit. Delivery is fire-and-forget via `asyncio.create_task` — explicitly an MVP design with the caveat that in-flight tasks are abandoned on process restart.

## GitHub Issues

| Issue | Title | Status |
|-------|-------|--------|
| (PR #67) | feat(api): outbound webhook notifications | merged |

## Content

### Storage — Mongo `webhooks` collection

(Note: outbound webhook subscriptions live in **MongoDB**, not Postgres — see `[[decision-postgres-mongo-storage-split]]`.)

Per-subscription fields:

- `tenant_id`, `name`, `url`, `events` (list of event names)
- `secret` (`whsec_` + 32 base62-encoded random bytes)
- `is_active`, `created_at`, `last_delivery_at`, `last_status`

**Cap:** 10 webhooks per tenant, enforced at creation.

**URL validation:** the same SSRF defense used for URL ingestion runs at registration time and at every delivery attempt — see `[[concept-ssrf-defense-url-ingestion]]`. Private/loopback/metadata IPs are blocked outright; only `http`/`https` schemes (HTTPS recommended).

### Signing — HMAC-SHA256 with timestamp

Per delivery:

```
sig_input = f"{epoch_seconds}.{json_body}"
sig       = hex(hmac_sha256(sig_input, key=webhook.secret))
header    = f"t={epoch_seconds},v1={sig}"
```

Header name: `Mongorag-Signature` (Stripe-style format). Tolerance: **300 seconds** of clock skew.

### Retry / DLQ semantics

`webhook_delivery.py`:

- **Max attempts:** 5
- **Backoff:** exponential — 2s, 4s, 8s, 16s, 32s
- **Retry on:** 5xx, 408, 429, network errors / timeouts
- **Terminal on:** any other 4xx (event will not be re-delivered)
- Each attempt's result (status code, latency, error string) is appended to the delivery audit row before the next attempt is scheduled, so a lost background task can be diagnosed.

### Delivery worker (MVP limitation)

Delivery runs as `asyncio.create_task(deliver_event(...))` from inside the API process — **not** Celery. Tradeoff:

- ✓ Zero infra cost; no extra queue
- ✗ In-flight tasks are abandoned if the API process restarts mid-attempt — the audit row records the abandonment but the delivery isn't resumed

This is documented as an MVP limitation; future hardening would move delivery onto a Celery queue (the same broker as ingestion) and use the audit row to drive replay.

### Delivery flow

1. Domain event happens in business code (`document.created`, etc.)
2. `webhook.dispatch_event(tenant_id, type, payload)` queries Mongo `webhooks` for active subscriptions matching `type`
3. For each match, an audit row is pre-created and `asyncio.create_task` spawns delivery
4. `webhook_delivery.deliver_event` POSTs with signature header; updates audit row per attempt; gives up after 5 attempts or on terminal 4xx

### Endpoints (`routers/webhooks.py`)

- `GET /api/v1/webhooks` — list subscriptions for the tenant
- `POST /api/v1/webhooks` — create (URL is SSRF-validated, secret is generated and returned **once**)
- `PATCH /api/v1/webhooks/{id}` — update name / events / active flag
- `DELETE /api/v1/webhooks/{id}` — soft-delete (sets `is_active=false`)
- `POST /api/v1/webhooks/{id}/test` — sends a synthetic delivery to verify the endpoint

All require JWT (dashboard-only) per `principal.require_jwt()`.

## Key Takeaways

- Stripe-style signing: `t=<epoch>,v1=<hex>` HMAC-SHA256 over `timestamp.json_body`, 300s tolerance.
- Retries: 5 attempts, exponential backoff 2/4/8/16/32 s. Terminal on 4xx (except 408/429).
- Same SSRF defense that protects URL ingestion runs at webhook registration AND at every delivery hop.
- `asyncio.create_task` fire-and-forget — abandoned on process restart. Documented MVP limitation; replay needs Celery.
- 10-webhook cap per tenant; secrets shown once at creation; soft-delete sets `is_active=false`.

## See Also

- [[concept-ssrf-defense-url-ingestion]] — same defenses applied to outbound URL targets
- [[concept-stripe-webhook-idempotency]] — *inbound* webhook idempotency (different direction, complementary pattern)
