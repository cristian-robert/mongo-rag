---
title: "Feature: Stripe Billing"
type: feature
tags: [feature, billing]
sources:
  - "git log: f1022e2 docs: add Stripe billing implementation plan (#10)"
  - "git log: 7547be1 docs: add Stripe billing integration design spec (#10)"
related: []
created: 2026-04-29
updated: 2026-04-29
status: draft
---

## Summary

Stripe-powered subscription billing for the MongoRAG SaaS. Design spec and implementation plan are merged (PRs #10); implementation is in progress. Tracks subscriptions per tenant, meters usage (queries, documents, storage), and enforces plan-based quotas.

## GitHub Issues

| Issue | Title | Status |
|-------|-------|--------|
| #10 | Stripe billing integration design spec + plan | docs merged |

## Key Decisions

- **Stripe Checkout for sign-up flow** — hosted, PCI burden on Stripe, fewer custom UI surfaces
- **Subscription tiers** — Free / Pro / Enterprise with quota enforcement at the query/ingestion layer
- **Webhook-driven state** — `subscriptions` collection is updated only from Stripe webhooks (signature-verified), never from the dashboard

## Implementation Notes

_(updated as the feature ships)_

- Storage: `subscriptions` collection — `{ stripe_customer_id, stripe_subscription_id, plan, status, current_period_end, usage, tenant_id }`
- Endpoints (planned):
  - `POST /api/v1/billing/checkout` — creates a Checkout Session, returns redirect URL
  - `POST /api/v1/billing/portal` — creates a Customer Portal session
  - `POST /api/v1/billing/webhooks/stripe` — webhook receiver (signature-verified)
- Quota enforcement is a FastAPI dependency that checks plan limits and returns `429 Too Many Requests` with a `Retry-After` header when exceeded (see `[[feature-usage-metering-rate-limiting]]`)

## Key Takeaways

- Webhook signature verification is non-negotiable — never trust unverified Stripe payloads
- Use `/stripe-best-practices` skill before touching this code
- Idempotency keys on every Stripe API call (Stripe retries are at-least-once)

## See Also

_(none yet — link auth and quota-enforcement articles when those exist)_
