---
date: 2026-04-30
type: session
scope: PRs #46 → #72 (26 merged PRs)
---

# Foundation Sprint — 26 PRs

Bulk capture of architectural shifts and patterns introduced during the foundation sprint that took the repo from a single-tenant RAG agent to a multi-tenant SaaS skeleton.

## Storage architecture pivot — Mongo + Postgres split

PRs: #45 (Supabase tenancy/identity/billing schema init), #46 (API key UI), #65 (web Supabase Auth), #66 (API JWT verify), #68 (Stripe webhooks Postgres idempotency), #70 (API key validation Postgres).

- Identity (`tenants`, `users`, `team_members`), authn/authz (api keys with `key_hash`, `permissions`), and billing (`subscriptions`, `stripe_events` for idempotency) live in **Postgres (Supabase)**.
- RAG content (`documents`, `chunks`, `conversations`, `messages`, embeddings) stays in **MongoDB Atlas** (vector search needs it).
- This is the most-violated assumption in older docs/comments — CLAUDE.md still listed all of them as Mongo collections.

## Auth pivot — NextAuth.js → Supabase Auth

PRs: #65 (web replace NextAuth with @supabase/ssr), #66 (FastAPI verifies Supabase JWT), #72 (drop stale NEXTAUTH_SECRET test).

- Web: `@supabase/ssr` cookies, server-component-friendly. Public key = `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, server key = `SUPABASE_SECRET_KEY`.
- API: bearer-token JWT verification using Supabase JWKS; produces a `Principal`.
- Two valid auth methods feed the same Principal: JWT (dashboard users) and API key (`mrag_*` widget/programmatic).

## Principal pattern — single tenant_id chokepoint (#69)

`apps/api/src/core/principal.py` is the security choke point. Every tenant-scoped DB call MUST source `tenant_id` from a `Principal`, never from request input.

Helpers:
- `get_principal` FastAPI dep — decodes JWT or API key, builds `Principal`.
- `tenant_filter(principal, **extra)` — Mongo filter dict; `tenant_id` always wins on collisions.
- `tenant_doc(principal, **fields)` — insert doc with locked `tenant_id`.
- `principal.require_jwt()` — for dashboard-only endpoints (key mgmt, billing, analytics).
- `principal.require_permission(p)` — for fine-grained API-key permissions.

A lint test enforces every Mongo call site either uses these helpers or is on a documented allow-list. Client-supplied `tenant_id` is rejected outright.

## Stripe webhook idempotency in Postgres (#68)

Webhook events stored in `stripe_events` table with the Stripe `event.id` as the primary key. Insert-or-skip pattern guards against duplicate delivery; the Stripe webhook handler is the only mutator of subscription state.

## Outbound webhook delivery (#67)

Customers register webhook endpoints; we sign payloads (HMAC-SHA256) and POST with retries + DLQ semantics. See `services/webhook_delivery.py` and `routers/webhooks.py`.

## URL ingestion + SSRF defense (#52)

`services/ingestion/` adds URL ingestion. Pre-fetch DNS resolution rejects RFC1918, loopback, link-local, and metadata-service IPs. Content-type and size limits enforced before parsing.

## RAG pipeline upgrades (#63)

- **Reranker**: pluggable interface in `services/rerank.py` (Cohere/Voyage/no-op).
- **Query rewriting**: `services/query_rewrite.py` — LLM-driven follow-up rewrite.
- **Inline citations**: `services/citations.py` — chunk attribution mapped to response spans.

## RAG quality eval harness (#56)

`apps/api/src/eval/` — golden Q/A set runner; reports recall@k, MRR, faithfulness scores. Must be run before merging changes that touch retrieval.

## Embeddable widget (#51)

`packages/widget/` — vanilla JS chat widget, SSE streaming, scoped CSS. API key authenticates; `bot_id` selects which bot config to use.

## Bot config + multi-tenant management (#53)

`bots` collection in Mongo: per-tenant chatbot configurations (system prompt, model, tools enabled, embed customization).

## Team management + RBAC (#64)

`team_members` table in Postgres with role enum (`owner`, `admin`, `member`). Role-checks in `services/team.py`; admin endpoints guarded.

## Analytics dashboard (#62)

`routers/analytics.py` + `services/analytics.py`: conversation counts, top queries, latency p95, costs per tenant.

## Document CRUD API (#54)

`routers/documents.py`: list/get/patch/delete + reingest. Cascading delete also removes chunks and embeddings.

## Usage metering + rate limiting (#49)

`services/rate_limit.py` (token-bucket in Redis), `services/usage.py` (per-tenant counters). Limits scale by plan tier.

## Marketing + onboarding (#60)

`apps/web/app/(marketing)` and `(onboarding)` — landing page, signup flow, first-bot setup wizard.

## Billing UI (#50, #48)

Plans catalog, checkout via Stripe-hosted page, customer portal link. Plans reflected in Postgres `subscriptions` table.

## Production Docker + GHCR (#59)

Multi-stage Dockerfiles for api/web/widget; GitHub Actions builds + pushes to GHCR on tag.

## Observability (#57)

`/ready` and `/healthz` endpoints, structured JSON logging via structlog with request context (tenant_id, request_id, route), Sentry integration.

## Security hardening (#58)

Pydantic input validation on every endpoint, CORS allowlist (no `*`), strict CSP, secret hygiene (`.env.example` only, env var validation on boot).

## DB backup + DR (#61)

Automated nightly Postgres dumps, Mongo Atlas snapshots, restore runbook in `docs/`.

## Comprehensive testing (#55)

pytest unit/integration split, Playwright e2e harness for web. Test users seeded from env (`TEST_USER_EMAIL`/`TEST_USER_PASSWORD`).

---

## Things to capture as wiki articles

High priority (created as stubs in this evolve):
1. `decision-postgres-mongo-storage-split.md`
2. `concept-principal-tenant-isolation.md`
3. `decision-supabase-auth-over-nextauth.md`
4. `concept-stripe-webhook-idempotency.md`
5. `concept-ssrf-defense-url-ingestion.md`

Lower priority (raw-only for now, expand on next `/kb compile`):
- Pluggable reranker / query rewrite / citations
- RAG eval harness
- Embeddable widget protocol
- Outbound webhook delivery
- Observability stack
- Backup & DR runbook
