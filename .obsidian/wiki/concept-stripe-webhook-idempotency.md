---
title: "Stripe webhook idempotency via Postgres"
type: concept
tags: [concept, billing, stripe, webhooks, idempotency, postgres]
sources:
  - "apps/api/src/services/stripe_webhook.py"
  - "apps/api/src/routers/stripe_webhooks.py"
  - "supabase/migrations/20260429200000_stripe_events.sql"
  - "supabase/migrations/20260429190107_init_tenancy.sql (subscriptions table)"
related:
  - "[[feature-stripe-billing]]"
  - "[[decision-postgres-mongo-storage-split]]"
created: 2026-04-30
updated: 2026-04-30
status: compiled
---

## Overview

Stripe delivers webhook events at-least-once. We make our handler idempotent by recording every received `event.id` in a Postgres `public.stripe_events` table whose primary key is the event id. Insert-or-skip is the entire idempotency check. Subscription mutations downstream are only executed when the insert was new.

## Content

### `stripe_events` table — actual schema

`supabase/migrations/20260429200000_stripe_events.sql`:

| Column | Type | Notes |
|---|---|---|
| `event_id` | text | PRIMARY KEY — Stripe `event.id` |
| `type` | text NOT NULL | e.g. `"checkout.session.completed"` |
| `received_at` | timestamptz DEFAULT now() | |
| `processed_at` | timestamptz NULL | filled after successful dispatch |
| `payload` | jsonb | redacted (PII scrubbed before insert) |

Indexes: `stripe_events_received_at_idx` (DESC), `stripe_events_type_idx`.

There is no surrogate id and no `tenant_id` column — events arrive before the tenant is known; the linkage is reconstructed from the payload during dispatch.

### Idempotency check (real code)

`apps/api/src/services/stripe_webhook.py:130-148`:

```sql
INSERT INTO public.stripe_events (event_id, type, payload)
VALUES ($1, $2, $3::jsonb)
ON CONFLICT (event_id) DO NOTHING
RETURNING event_id
```

`record_event(conn, event)` returns `True` if a row was inserted (new event), `False` if the conflict suppressed the insert (duplicate). The caller in `process_event()` (line ~392) skips all side effects on `False`, so retries from Stripe are no-ops.

### Signature verification (real code)

`stripe_webhook.py:68-92` calls `stripe.Webhook.construct_event(payload, sig_header, secret, tolerance=300)`. The signing secret is `deps.settings.stripe_webhook_secret` (env `STRIPE_WEBHOOK_SECRET`, `whsec_...` format). Failures raise `WebhookSignatureError` → HTTP **400** (never 500), so Stripe will retry with backoff.

### Subscription mutation as the only side effect

`public.subscriptions` is the downstream target:

| Column | Type | Notes |
|---|---|---|
| `tenant_id` | uuid | PRIMARY KEY — one subscription per tenant, FK to tenants |
| `stripe_customer_id` | text UNIQUE | nullable |
| `stripe_subscription_id` | text UNIQUE | nullable |
| `plan` | enum | free / starter / pro / enterprise |
| `status` | enum | trialing / active / past_due / canceled / incomplete / incomplete_expired / unpaid / paused |
| `current_period_end` | timestamptz | |
| `usage` | jsonb DEFAULT `{}` | |
| `updated_at` | timestamptz | trigger-managed |

`STRIPE_STATUS_MAP` (in `stripe_webhook.py:52-61`) maps Stripe status strings to the local enum. Service-role only writes — neither the user nor the dashboard mutates `subscriptions` directly. The webhook handler is the **only** mutator.

### Handler control flow

1. Router `routers/stripe_webhooks.py` receives the request
2. `construct_event` verifies signature → raises 400 on failure
3. `record_event(conn, event)` inserts; returns False → 200 OK with no side effects
4. Returns True → `process_event()` dispatches by `event.type`, mutating `subscriptions` if applicable
5. After successful dispatch, `processed_at` is updated

If `process_event()` itself fails after the insert succeeded, the row is kept (no `processed_at`) so a retry of the same Stripe event is dropped at step 3. That's a **deliberate trade-off**: at-least-once delivery becomes at-most-once *side-effect*, with the cost that a stuck event needs operator intervention. For multi-step dispatches, make each step idempotent (upsert by `subscription.id` etc.).

## Key Takeaways

- Stripe `event.id` as primary key + `ON CONFLICT DO NOTHING RETURNING` = the idempotency check.
- The `stripe_events` table has both `received_at` (auto) and `processed_at` (set post-dispatch); a row without `processed_at` indicates a stuck event.
- Always verify signature before any DB write; failure path returns 400 (Stripe will retry).
- Webhook handler is the *only* place that writes to `public.subscriptions` — the UI funnels users through Stripe checkout/portal and reacts to webhook results.
- The table is in Postgres because Stripe events need transactional semantics with the subscription state they update; no Mongo path exists.

## See Also

- [[feature-stripe-billing]] — the broader feature article (plans catalog, checkout flow, billing UI)
- [[decision-postgres-mongo-storage-split]] — why `stripe_events` lives in Postgres, not Mongo
