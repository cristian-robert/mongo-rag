# Wiki Index

_Last updated: 2026-05-01 — 26 articles_

## Concepts

- [[hybrid-rrf-search]] — Three-tier hybrid search (vector + text + RRF fusion) for grounded RAG retrieval
- [[multi-tenancy-tenant-isolation]] — Query-layer tenant isolation: every Mongo/Postgres query filters by `tenant_id`
- [[concept-principal-tenant-isolation]] — `Principal` chokepoint, `tenant_filter`/`tenant_doc`, `RejectClientTenantIdMiddleware`, AST audit test
- [[concept-stripe-webhook-idempotency]] — Postgres `stripe_events` PK on `event.id` + `ON CONFLICT DO NOTHING RETURNING`
- [[concept-ssrf-defense-url-ingestion]] — Block-list of private/metadata IPs, MIME allow-list, redirect re-validation
- [[concept-celery-ingestion-worker]] — Celery + Redis ingestion tasks; JSON serializer; retry policies
- [[concept-rate-limiting-fixed-window]] — Fixed-window limiter with Redis backend; rollback on rejection
- [[concept-observability-stack]] — JSON logs, ContextVars, redaction, Sentry, x-request-id, /health vs /ready

## Features

- [[feature-rag-agent]] — Pydantic AI agent with hybrid search tools, conversation history, streaming responses
- [[feature-document-ingestion]] — Docling-based ingestion pipeline: parse → chunk → embed → store
- [[feature-rag-pipeline-enhancements]] — Pluggable reranker, query rewriting, inline citations
- [[feature-rag-eval-harness]] — JSONL golden set, recall@k/MRR/nDCG@k metrics, CI threshold gates
- [[feature-api-key-management]] — `mrag_*` API keys, bcrypt hashing, Postgres-default lookup
- [[feature-stripe-billing]] — Subscription tiers, plans catalog, Stripe-hosted checkout
- [[feature-usage-metering-rate-limiting]] — Per-tenant counters scaled by plan
- [[feature-embeddable-widget]] — IIFE bundle, closed Shadow DOM, SSE chat over `mrag_*` Bearer
- [[feature-outbound-webhooks]] — HMAC-SHA256 signing, exp-backoff retry, fire-and-forget delivery
- [[feature-team-management-rbac]] — Owner/admin/member/viewer roles, last-owner protection, hashed invitations
- [[feature-bot-configuration]] — Per-tenant chatbots with system prompts, document filter, widget styling
- [[feature-analytics-dashboard]] — Per-tenant `$facet` analytics over conversations

## Decisions

- [[decision-pydantic-ai-over-langchain]] — Chose Pydantic AI for native FastAPI fit and lighter footprint
- [[decision-postgres-mongo-storage-split]] — Identity/billing in Postgres, RAG in Mongo (mid-migration)
- [[decision-supabase-auth-over-nextauth]] — Supabase primary; legacy NextAuth HS256 path retained
- [[decision-blobstore-handoff]] — `BlobStore` Protocol + `scheme://bucket/key` URIs across API → Celery worker
- [[decision-deploy-fly-vercel]] — Vercel (web) + Fly Machines (api + worker) + Upstash + Supabase Storage

## Guides

_(none yet — created as needed)_

## Tooling

- [[tooling-test-web-app]] — `apps/testWebApp` — Next.js host page on port 3101 for manual widget verification (stub)

## Comparisons

_(none yet — created as needed)_

## References

_(none yet — created as needed)_

## Session Learnings

_(captured as raw notes in `raw/sessions/` — pending compile)_
