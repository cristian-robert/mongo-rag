# Architecture Design — 2026-03-29

## Context

Issue #1: Define system architecture and technical decisions for MongoRAG — a multi-tenant AI chatbot SaaS powered by RAG.

Based on analysis of [coleam00/MongoDB-RAG-Agent](https://github.com/coleam00/MongoDB-RAG-Agent) reference implementation (2,378 lines of Python, 10 source files).

## Decisions Made

1. **Monorepo** — `apps/api` (FastAPI/Python), `apps/web` (Next.js/TypeScript), `packages/widget` (embeddable JS)
2. **Pydantic AI** for agent orchestration — lightweight, type-safe, native FastAPI fit
3. **Shared database with query-layer tenant isolation** — `tenant_id` on every collection, enforced via FastAPI dependencies
4. **Dual auth** — NextAuth.js sessions (dashboard), API keys with `mrag_` prefix (widget/programmatic)
5. **Hybrid RRF search** — concurrent semantic + text search, merged with Reciprocal Rank Fusion (k=60)
6. **SSE streaming** for chat responses — simpler than WebSockets, CDN-friendly
7. **Vercel + Railway** as primary deployment — Docker Compose as self-hosted alternative
8. **Dev ports** — `localhost:3100` (web), `localhost:8100` (api)

## Reuse Strategy

Copy and adapt core modules from coleam00/MongoDB-RAG-Agent:
- `tools.py` — add tenant_id filtering
- `ingestion/` — chunker and embedder as-is, ingest adapted for tenant_id + content_hash
- `providers.py`, `settings.py` — as-is or extended
- `agent.py` — wired to FastAPI instead of CLI
- Drop: `cli.py`, `examples/`, `documents/`, `test_scripts/`

## Deliverable

`docs/architecture.md` — full architecture document covering system diagram, component boundaries, data flow, multi-tenancy, auth, database schema, deployment, technical decisions, and reuse plan.
