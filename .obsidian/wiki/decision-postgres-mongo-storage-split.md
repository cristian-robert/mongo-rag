---
title: "Decision: Postgres + MongoDB storage split (mid-migration state)"
type: decision
tags: [decision, architecture, database, supabase, mongodb, multi-tenancy]
sources:
  - "supabase/migrations/20260429190107_init_tenancy.sql"
  - "supabase/migrations/20260429200000_stripe_events.sql"
  - "apps/api/src/migrations/versions/0001_baseline_indexes.py"
  - "apps/api/src/services/{usage,team,bot,analytics,webhook}.py"
  - "PRs #45, #46, #66, #68, #70 (foundation sprint, 2026-04-29)"
related:
  - "[[multi-tenancy-tenant-isolation]]"
  - "[[concept-principal-tenant-isolation]]"
  - "[[decision-supabase-auth-over-nextauth]]"
  - "[[concept-stripe-webhook-idempotency]]"
created: 2026-04-30
updated: 2026-04-30
status: compiled
---

## Overview

The data model is split between Supabase Postgres and MongoDB Atlas, but the split is **partial and mid-migration**, not clean. Supabase Postgres is the authoritative store for new identity / billing / API keys. MongoDB still hosts RAG content (its real strength via vector search) and a parallel legacy stack for several domains the migration has not yet touched.

## Content

### What lives where (verified against migrations and service code)

**Postgres (Supabase) — authoritative**

| Table | Migration | Notes |
|---|---|---|
| `public.tenants` | `20260429190107_init_tenancy.sql` | id (uuid), slug (citext unique), name, plan (enum free/starter/pro/enterprise), settings (jsonb) |
| `public.profiles` | same | id (uuid PK FK auth.users), tenant_id (FK), email (citext), role (enum owner/admin/member/viewer). NOT a `users` table — `profiles` 1:1 with Supabase `auth.users`. |
| `public.api_keys` | same | id, tenant_id, created_by, name, prefix (indexed), key_hash (bcrypt rounds=12, unique), last_used_at, revoked_at |
| `public.subscriptions` | same | tenant_id PK FK tenants (one subscription per tenant), stripe_customer_id, stripe_subscription_id, plan, status (8-value enum), current_period_end, usage (jsonb), updated_at. Service-role-only writes. |
| `public.stripe_events` | `20260429200000_stripe_events.sql` | event_id (text PK = Stripe `event.id`), type, received_at, processed_at, payload (jsonb redacted) |

Postgres helpers: `current_tenant_id()`, `current_user_role()` (SECURITY DEFINER). Trigger `on_auth_user_created` auto-provisions tenant + profile + free subscription on Supabase signup. RLS enabled on all tables; service-role bypasses for the FastAPI backend.

**MongoDB Atlas — RAG content (canonical)**

| Collection | Notes |
|---|---|
| `documents` | tenant_id, title, source, content, content_hash (SHA256), version, status, error_message, chunk_count, metadata, timestamps |
| `chunks` | _id deterministic SHA256(source\|version\|index\|hash), tenant_id, document_id, content, embedding[1536], chunk_index, heading_path, content_type, embedding_model, token_count |
| `conversations` | tenant_id, messages[], indexed by tenant_id + updated_at |
| `bots` | tenant-scoped chatbot config (system prompt, model, widget config, document filter) |

Indexes (`apps/api/src/migrations/versions/0001_baseline_indexes.py`): `chunks_tenant_doc`, `chunks_tenant_chunkid_uq` (unique), `chunks_tenant_created`, `documents_tenant_{source,hash,created}`. Vector + Atlas Search indexes are NOT in migrations — applied via Atlas UI / `apps/api/scripts/setup_indexes.py`.

**MongoDB — legacy / not-yet-migrated**

These still live in Mongo even though identity/billing has moved to Postgres:

- `users` (legacy, distinct from Postgres `profiles`)
- `tenants` (legacy, distinct from Postgres `tenants`)
- `invitations` — team invites, SHA-256 hashed tokens
- `webhooks` — outbound webhook subscriptions
- `usage` — per-`(tenant_id, period_key=YYYY-MM)` counters
- `api_keys` — legacy fallback path, used only when `API_KEY_BACKEND=mongo` (emergency rollback)

The `services/api_key.py` router defaults to Postgres but retains the Mongo path; `services/team.py`, `services/bot.py`, `services/webhook.py`, `services/usage.py` still read from Mongo.

### Migration runners

- **Mongo:** custom runner at `apps/api/src/migrations/runner.py`, tracks `_migrations` collection. CLI: `python -m src.migrations.cli {status|up|down}`. Refuses prod URIs unless `MONGORAG_ALLOW_PROD=1`.
- **Postgres:** Supabase CLI applies SQL files in `supabase/migrations/`. Schema changes flow through Supabase, not the Mongo runner.

### Why a split (and why partial)

- **Postgres earns its place** for identity/billing because of FK constraints, transactional updates, status enums, RLS, and Stripe `event.id` as a natural primary key for idempotency.
- **Mongo earns its place** for RAG content because of `$vectorSearch` and `$search` (Atlas Search), nested message arrays, and schemaless bot/widget config blobs.
- **Why partial:** the foundation sprint moved auth (PR #66), api_keys (PR #70), Stripe (PR #68), and the tenancy schema (PR #45). Team, bots, webhooks, usage, and analytics still talk to Mongo. They will be migrated as features warrant; routine Mongo reads are not a security problem because tenant isolation is enforced at the Principal chokepoint regardless of store.

### Reading rules

- **Identity / role / billing decisions:** read from Postgres. The Supabase JWT is the source of truth; `profiles.role` overrides any stale claim in `/api/v1/auth/me`.
- **RAG queries:** Mongo, with tenant filter pushed into the search operator (never post-filter).
- **Cross-store transactions:** none. Postgres and Mongo are written in separate awaits; no distributed-transaction layer. Each domain owns its store.

## Key Takeaways

- Identity/billing in **Postgres**: `tenants`, `profiles` (NOT `users`), `api_keys` (bcrypt), `subscriptions`, `stripe_events`.
- RAG content in **Mongo**: `documents`, `chunks` (1536-dim), `conversations`, `bots`.
- **Mid-migration:** team, bot, webhook, usage, analytics, plus a legacy `api_keys` fallback path, still live in Mongo. Don't assume the split is clean.
- Two migration runners: custom Mongo CLI for index migrations; Supabase CLI for SQL schema.
- Tenant isolation is enforced uniformly via the Principal chokepoint; the choice of store does not affect that boundary.

## See Also

- [[concept-principal-tenant-isolation]] — chokepoint that makes the split safe regardless of store
- [[decision-supabase-auth-over-nextauth]] — auth that produces the JWT-backed Principal (note: NextAuth path is NOT fully removed)
- [[multi-tenancy-tenant-isolation]] — broader tenant-isolation context, lists which tables/collections are tenant-scoped
- [[concept-stripe-webhook-idempotency]] — concrete Postgres-side pattern (stripe_events table) enabled by this split
