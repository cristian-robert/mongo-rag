# Knowledge Base Health Report

_Generated: 2026-04-30 (post coverage-pass)_

## Stats

| Metric | Count |
|--------|-------|
| Total articles | 23 |
| Compiled / active | 22 |
| Draft | 1 (`feature-stripe-billing.md`) |
| Stubs | 0 |

## Coverage pass — what changed

**Driver:** user asked whether documentation was based on actual code exploration. It wasn't. 7 parallel `Explore` agents read the real implementation in: RAG pipeline, billing, ingestion + SSRF, auth + Principal, backend services, web frontend, widget + infra.

**Articles rewritten** (factual corrections after agent reports):

1. `decision-postgres-mongo-storage-split.md` — earlier version implied a clean split; reality is a **partial migration**. Mongo still hosts `users` (legacy), `tenants` (legacy), `invitations`, `webhooks`, `usage`, and an `api_keys` fallback path.
2. `concept-principal-tenant-isolation.md` — corrected to note **two Principal classes** (`core.principal.Principal` and `core.authz.Principal`), `tenant_filter` actively overrides (with warning) rather than rejecting, middleware scans recursively to depth 5 with 1 MiB cap, audit allow-list has ~17 entries.
3. `decision-supabase-auth-over-nextauth.md` — corrected: **NextAuth was NOT fully replaced**. Both JWT verification paths (Supabase JWKS RS256 + legacy NextAuth HS256) coexist with token-shape routing. Auth router has its own credential endpoints.
4. `concept-stripe-webhook-idempotency.md` — replaced fabricated SQL with the real schema from `supabase/migrations/20260429200000_stripe_events.sql`. Real query: `INSERT … ON CONFLICT (event_id) DO NOTHING RETURNING event_id`. `processed_at` set post-dispatch.
5. `concept-ssrf-defense-url-ingestion.md` — corrected: it's **block-listing**, not allow-listing. Added the explicit metadata-host set, scheme allow-list, MIME allow-list, URL credential rejection, 2048-char URL cap, and the documented DNS-rebinding TOCTOU caveat.

**Articles created** (10 new, all compiled):

- `concept-celery-ingestion-worker.md` — Celery + Redis (not asyncio BackgroundTasks)
- `feature-rag-pipeline-enhancements.md` — reranker / query rewrite / citations
- `feature-rag-eval-harness.md` — JSONL dataset, metrics, CI threshold gates
- `feature-embeddable-widget.md` — IIFE bundle, closed Shadow DOM, SSE
- `feature-outbound-webhooks.md` — HMAC-SHA256, exp backoff, fire-and-forget MVP
- `feature-team-management-rbac.md` — owner/admin/member/viewer, last-owner protection
- `feature-bot-configuration.md` — per-bot prompt + widget + document filter
- `feature-analytics-dashboard.md` — `$facet` over `conversations`
- `concept-rate-limiting-fixed-window.md` — fixed-window (not token-bucket); InMemory + Redis backends
- `concept-observability-stack.md` — JSON logs, ContextVars, redaction, Sentry, /health vs /ready

**Architect-agent KB:** `.claude/agents/architect-agent/index.md` rewritten end-to-end. The previous version listed Postgres tables as Mongo collections, said "NextAuth.js for dashboard auth", and missed ~10 modules.

## Structural Issues

### Orphaned Articles
- None — every article has at least one `related:` entry and at least one inbound link.

### Broken Wikilinks
- None detected.

### Old Stubs (>30 days)
- None.

### Incomplete Frontmatter
- None.

## Content Issues

### Duplicates / Differentiation
- `multi-tenancy-tenant-isolation.md` (broad concept) vs `concept-principal-tenant-isolation.md` (implementation chokepoint) — kept both, cross-linked. Differentiated.
- `concept-rate-limiting-fixed-window.md` (algorithm + interface) vs `feature-usage-metering-rate-limiting.md` (the higher-level feature) — kept both, cross-linked.

### Inconsistencies Resolved
- `multi-tenancy-tenant-isolation.md` previously listed `api_keys / users / subscriptions` as Mongo collections — fixed in earlier compile.
- 5 newly-rewritten articles now match real code.

### Stale Sources
- None.

## Suggestions

### Possibly missing
- A dedicated `feature-document-crud-api.md` (today documented inside `feature-document-ingestion.md`)
- A dedicated `feature-chat-endpoint.md` covering both REST/SSE and WebSocket-with-ticket auth
- A `decision-celery-over-asyncio-tasks.md` if the asyncio-task fire-and-forget pattern in outbound webhooks is migrated to Celery

### Stale Articles
- None.

## Karpathy Lint-Pass Findings (Step 7d)

1. **Resolved drift across 5 prior articles** — all updated against real source files (path-and-line-cited where useful).
2. **Architect-agent KB stale** — rewritten in this pass.
3. **CLAUDE.md MongoDB Collections section** — fixed in the prior `/evolve` run; verified still consistent.
4. **No speculative edits** — every change traceable to a specific file or migration.
