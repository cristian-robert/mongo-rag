# MongoRAG Architecture Index

_Last verified: 2026-04-30 (post-foundation-sprint coverage pass)_

## Backend Layout (apps/api/src/)

### Core
- `main.py` — FastAPI app, mounts routers, runs Sentry init + observability + middleware
- `core/principal.py` — `Principal` dataclass (frozen, JWT + API key) + `tenant_filter` / `tenant_doc` helpers; **single source of truth for `tenant_id`**
- `core/authz.py` — legacy dashboard-only `Principal` (JWT-only). Both classes coexist; prefer `core.principal.Principal` for new code
- `core/middleware.py` — `RejectClientTenantIdMiddleware` (path/query/JSON-body recursive scan, 1 MiB cap, depth 5)
- `core/supabase_auth.py` — Supabase JWKS verifier (RS256/ES256 etc., issuer + audience pinned)
- `core/security.py` — legacy NextAuth HS256 verifier (still wired; routed by token-shape `iss` peek)
- `core/observability.py` — JSON log formatter, ContextVar-injected request_id/tenant_id/user_id, redaction, Sentry init
- `core/request_logging.py` — `x-request-id` middleware, sanitized exception handlers
- `core/dependencies.py`, `core/deps.py` — DI for DB connections, settings, agent deps
- `core/settings.py` — Pydantic Settings (all env vars)

### Auth
- `auth/api_keys.py` — `mrag_*` prefix + 48-byte body, **bcrypt (12 rounds)** hash. Postgres-default lookup; constant-time bcrypt over candidates; Mongo SHA-256 fallback when `API_KEY_BACKEND=mongo`
- `routers/auth.py` — `/signup`, `/login`, `/forgot-password`, `/reset-password`, `/me`, `/ws-ticket` (rate-limited, enumeration-safe)

### Retrieval / RAG
- `services/search.py` — hybrid RRF (semantic + Atlas Search), tenant filter pushed into both operators
- `services/retrieval.py` — orchestrator (rewrite → search → rerank → cite)
- `services/rerank.py` — `Reranker` Protocol; `CohereReranker` (rerank-3.5) and `LocalCrossEncoderReranker` (sentence-transformers in thread pool); factory returns None when off
- `services/query_rewrite.py` — vague-query detection (≤25 chars or markers); heuristic + Pydantic-AI LLM modes; expansions merged via RRF
- `services/citations.py` — `Citation` Pydantic model; `[n]` regex extraction
- `services/agent.py` — Pydantic AI `Agent` factory (`create_rag_agent`)
- `services/chat.py` — `ChatService.handle_message` (sync) + `handle_message_stream` (SSE)
- `eval/` — JSONL dataset, metrics (recall@k, MRR, nDCG@k, hit@k, substring_match), optional LLM judge, CLI runner with `--min-*` CI gates

### Ingestion (Celery + Redis)
- `worker.py` — Celery app; `ingest_document` (3 retries, 10–90s backoff) + `ingest_url` (2 retries, 15–120s backoff); JSON serializer, `acks_late=true`, `prefetch=1`
- `services/ingestion/chunker.py` — Docling HybridChunker (max 512 tokens), simple sliding-window fallback
- `services/ingestion/embedder.py` — AsyncOpenAI, batch=100, `text-embedding-3-small` (1536-dim)
- `services/ingestion/url_loader.py` — `validate_url` + `_resolve_and_check_host` SSRF defense (block-list of private/loopback/link-local/metadata IPs + explicit metadata host set, scheme allow-list `http`/`https`, MIME allow-list, size cap, redirect re-validation)
- `services/ingestion/ingest.py` — pipeline orchestration

### Billing (Postgres + Stripe)
- `services/stripe_webhook.py` — `construct_event` (300s tolerance), `record_event` (`ON CONFLICT DO NOTHING RETURNING`), `process_event` (only side-effect path)
- `services/billing.py` + `routers/billing.py` — `/plans` (public), `/checkout` (owner-only)
- `models/billing.py` — `PLAN_LIMITS`, `MODEL_CATALOG`, `DISPLAY_PRICES_CENTS`, `resolve_stripe_price_id` (env `stripe_price_{plan}_{tier}`)
- `routers/stripe_webhooks.py` — webhook entry

### Other services
- `services/rate_limit.py` — fixed-window; `InMemoryRateLimiter` + `RedisRateLimiter` Protocol; key `ratelimit:{key}:{bucket}`; rollback on rejection
- `services/usage.py` — Mongo `usage` collection, per-`(tenant_id, period_key=YYYY-MM)` counters; reserve-and-rollback for queries; pre-check for documents
- `services/team.py` — roles `OWNER/ADMIN/MEMBER/VIEWER`; last-owner two-phase protection; SHA-256-hashed single-use invitations (default 168h TTL, email-match required)
- `services/bot.py` — `bots` Mongo collection; per-bot prompt/welcome/widget/document_filter; 50 cap/tenant; public read for widget branding
- `services/analytics.py` — `$facet` aggregations over `conversations` (overview, timeseries, queries, conversation_detail); window 1–365 days, page 1–100
- `services/webhook.py` + `services/webhook_delivery.py` — outbound webhooks; `whsec_` secret; HMAC-SHA256 over `timestamp.json_body`; `t=<epoch>,v1=<hex>` header (Stripe-style); 5 attempts exp backoff 2/4/8/16/32 s; **fire-and-forget `asyncio.create_task` — abandoned on process restart (MVP)**; same SSRF defenses as URL ingestion
- `services/api_key.py`, `services/auth.py`, `services/ws_ticket.py` (30s lifetime, single-use, SHA-256-hashed), `services/conversation.py`

### Routers (mount prefix `/api/v1/`)
- `auth`, `keys`, `team`, `billing`, `stripe_webhooks`, `webhooks`
- `chat` (REST `POST /chat` SSE-or-JSON + WebSocket `/chat/ws?ticket=`), `documents`, `ingest`, `bots`, `analytics`, `usage`, `health`

### Migrations
- **Mongo:** `apps/api/src/migrations/versions/0001_baseline_indexes.py` (only one currently). Custom runner at `migrations/runner.py`; `_migrations` collection tracks applied versions. CLI `python -m src.migrations.cli {status|up|down}`. Refuses prod URI unless `MONGORAG_ALLOW_PROD=1`.
- **Postgres:** `supabase/migrations/20260429190107_init_tenancy.sql` (tenants, profiles, api_keys, subscriptions, RLS, helper fns, on_auth_user_created trigger), `20260429200000_stripe_events.sql` (idempotency table). Applied via Supabase CLI.
- **Atlas Search / Vector indexes:** NOT in migrations — `apps/api/scripts/setup_indexes.py` or Atlas UI.

## Test Web App (apps/testWebApp/, Next.js 16.2.4, React 19.2.4)

Dev-only widget integration test host. No auth, no Supabase, no shadcn. Loads `packages/widget/dist/widget.js` to simulate a third-party site. Runs on **port 3101**.

- Domain file: `frontend/test-web-app.md`
- Related: `[[feature-embeddable-widget]]`, `[[tooling-test-web-app]]`

## Frontend Layout (apps/web/, Next.js 16.2.1, React 19.2.4)

### Route groups
- `app/(marketing)/` — `/` (landing), `/pricing`
- `app/(auth)/` — `/login`, `/signup`, `/forgot-password`, `/reset-password`
- `app/(dashboard)/dashboard/` — overview, `documents`, `api-keys`, `billing`, `analytics`, `bots`, `team`, `webhooks`
- `app/(onboarding)/onboarding/` — `welcome` → `document` → `api-key` → `embed`
- `app/api/` — Next.js route handlers: `documents/upload` (proxy to FastAPI), `auth/{callback,signout}`, `invite/[token]/accept`

### Auth (Supabase via @supabase/ssr)
- `lib/supabase/client.ts` — browser client (`createBrowserClient`)
- `lib/supabase/server.ts` — server client (`createServerClient<Database>`, `cookies()` from `next/headers`)
- `lib/supabase/middleware.ts` — `updateSession` refreshes on every request
- `middleware.ts` — `updateSession` + route protection + `x-request-id`
- `lib/auth.ts` — `getSession()`, `getAccessToken()`, `requireSession()` (cached server fns)
- `lib/api-client.ts` — `apiFetch()` forwards Supabase access token as `Authorization: Bearer <jwt>` to FastAPI

### Stack
- shadcn/ui + Tailwind, React Hook Form + Zod, sonner, lucide-react
- `next.config.ts` — `output: standalone`, CSP (allows Stripe, Supabase, FastAPI base URL; `frame-ancestors 'none'`), HSTS, X-Frame-Options
- Document upload: client → `/api/documents/upload` (Next route validates ext/MIME/size, mints token) → FastAPI `/api/v1/documents/ingest`

## Widget (packages/widget/)

- `src/index.ts` — entry, parses `data-*` attrs + `window.MongoRAG`, validates, mounts via closed Shadow DOM
- `src/api.ts` — SSE via `fetch` + `ReadableStream` to `POST /api/v1/chat`, `Authorization: Bearer mrag_*`
- `src/styles.ts` — `.mrag-`-prefixed CSS, `--mrag-primary` variable
- esbuild IIFE bundle (`format=iife --target=es2020 --minify`)
- Embedding: `<script src="…/widget.js" data-api-key="mrag_…" data-bot-id="…">`
- Hosting: nginx:1.27.3-alpine, port 8080, `/healthz`, `Cache-Control: public, max-age=300`, CORS `*`

## Storage Layout

### Postgres (Supabase) — authoritative for identity / billing
| Table | Notes |
|---|---|
| `public.tenants` | id (uuid), slug (citext unique), name, plan enum (free/starter/pro/enterprise), settings (jsonb) |
| `public.profiles` | id (PK FK auth.users), tenant_id (FK), email (citext), role enum (owner/admin/member/viewer). NOT `users`. |
| `public.api_keys` | id, tenant_id, created_by, name, prefix (indexed), key_hash (bcrypt unique), last_used_at, revoked_at |
| `public.subscriptions` | tenant_id PK FK, stripe_customer_id (unique), stripe_subscription_id (unique), plan, status enum (8 values), current_period_end, usage (jsonb) |
| `public.stripe_events` | event_id (text PK = Stripe event.id), type, received_at, processed_at, payload (jsonb redacted) |

RLS enabled on all tables; service-role bypasses. `current_tenant_id()` / `current_user_role()` SECURITY DEFINER. `on_auth_user_created` trigger auto-provisions tenant + profile + free subscription on Supabase signup.

### MongoDB Atlas — RAG content (canonical)
| Collection | Notes |
|---|---|
| `documents` | tenant_id, title, source, content, content_hash (SHA256), version, status, error_message, chunk_count, metadata, timestamps |
| `chunks` | _id deterministic, tenant_id, document_id, content, embedding[1536], chunk_index, heading_path, content_type, embedding_model, token_count |
| `conversations` | tenant_id, messages[], indexed by tenant_id + updated_at |
| `bots` | tenant-scoped chatbot config |

### MongoDB — legacy / not-yet-migrated
- `users`, `tenants` (legacy duplicates), `invitations`, `webhooks`, `usage`, `api_keys` (fallback when `API_KEY_BACKEND=mongo`)

### Mongo indexes (`migrations/versions/0001_baseline_indexes.py`)
- `chunks_tenant_doc`, `chunks_tenant_chunkid_uq` (unique), `chunks_tenant_created`
- `documents_tenant_source`, `documents_tenant_hash`, `documents_tenant_created`
- Vector + Atlas Search indexes applied via Atlas UI / `scripts/setup_indexes.py`

## Key Decisions

- **Pydantic AI** over LangChain (lighter, native FastAPI fit) — see `[[decision-pydantic-ai-over-langchain]]`
- **Postgres + Mongo split** (mid-migration; identity/billing in Postgres, RAG in Mongo, several domains still in Mongo) — see `[[decision-postgres-mongo-storage-split]]`
- **Supabase Auth as primary, NextAuth retained** as legacy fallback — see `[[decision-supabase-auth-over-nextauth]]`
- **Principal-based tenant isolation** — see `[[concept-principal-tenant-isolation]]`
- **API keys** — `mrag_*` prefix, **bcrypt (12 rounds)**, Postgres-default lookup
- **Celery + Redis** for ingestion (not FastAPI BackgroundTasks)
- **Outbound webhooks via `asyncio.create_task`** (MVP — abandoned on restart)
- **Stripe `event.id` as Postgres PK** — natural idempotency
- **Block-list SSRF defense** (private/metadata IPs blocked, not allow-listed)

## Infra / CI

- **GHCR pipeline** (`.github/workflows/deploy.yml`): builds + pushes `ghcr.io/<owner>/mongo-rag/{api,web,widget}` on main + semver tags + dispatch. Trivy scan, SBOM (Syft SPDX-JSON), cosign keyless OIDC signing, GHA cache, SLSA provenance.
- **CI** (`.github/workflows/ci.yml`): ruff/mypy/pytest unit, pnpm lint/tsc/build/test, opt-in Playwright e2e, Docker smoke build.
- **Backups** (`.github/workflows/backup.yml`): daily 03:17 UTC; manual dispatch all/mongo/postgres; `scripts/backup/{mongo,postgres}_backup.sh` → S3.
- **DR runbook:** `docs/disaster-recovery.md` (RPO/RTO targets, restore drills, scripts/backup/{mongo,postgres}_restore.sh).

## Dockerfiles

- API: python:3.11.11-slim-bookworm, multi-stage, port 8100, tini PID 1, non-root uid 1001, urllib healthcheck
- Web: node:22.14.0-bookworm-slim, multi-stage, `output: standalone`, port 3100, non-root uid 1001
- Widget: nginx:1.27.3-alpine runtime (build with node:22.12-alpine), port 8080, non-root uid 1001
