# MongoRAG System Architecture

## Overview

Multi-tenant AI chatbot SaaS powered by RAG. Customers sign up, upload documents, get an embeddable script tag, and install a chatbot on their website that answers questions grounded in their own data.

Built on [coleam00/MongoDB-RAG-Agent](https://github.com/coleam00/MongoDB-RAG-Agent) — adapted and extended for multi-tenant SaaS.

## System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      Customer Website                        │
│  <script src="https://cdn.mongorag.com/widget.js"           │
│          data-api-key="mrag_..." />                          │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTPS (API key auth)
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  FastAPI Backend (apps/api/)              Railway             │
│  ┌────────────┐ ┌──────────┐ ┌─────────────────────────┐    │
│  │ /api/v1/   │ │ Agent    │ │ Ingestion Pipeline      │    │
│  │ chat       │ │ Pydantic │ │ Docling → Chunk → Embed │    │
│  │ documents  │ │ AI +     │ │ → MongoDB               │    │
│  │ ingest     │ │ Tools    │ └─────────────────────────┘    │
│  │ keys       │ │ (RRF)   │                                  │
│  │ billing    │ └──────────┘                                  │
│  └─────┬──────┘                                              │
└────────┼─────────────────────────────────────────────────────┘
         │ HTTPS (NextAuth session / API key)
         ▼
┌──────────────────────────────────────────────────────────────┐
│  Next.js Frontend (apps/web/)            Vercel              │
│  ┌────────────────┐ ┌──────────────┐ ┌─────────────────┐    │
│  │ (marketing)    │ │ (auth)       │ │ (dashboard)     │    │
│  │ /, /pricing    │ │ /login       │ │ /documents      │    │
│  │ /docs          │ │ /register    │ │ /api-keys       │    │
│  └────────────────┘ └──────────────┘ │ /billing        │    │
│                                       │ /settings       │    │
│                                       └─────────────────┘    │
└──────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────┐
│  MongoDB Atlas                                               │
│  documents | chunks (+ vector_index) | tenants | users       │
│  api_keys | conversations | subscriptions                    │
└──────────────────────────────────────────────────────────────┘
```

## Monorepo Structure

**Decision: Monorepo** with `apps/` and `packages/` structure.

```
mongo-rag/
├── apps/
│   ├── api/                 # FastAPI backend (Python, uv)
│   │   └── src/
│   │       ├── agent.py
│   │       ├── tools.py
│   │       ├── providers.py
│   │       ├── settings.py
│   │       ├── dependencies.py
│   │       ├── prompts.py
│   │       └── ingestion/
│   │           ├── ingest.py
│   │           ├── chunker.py
│   │           └── embedder.py
│   └── web/                 # Next.js frontend (TypeScript, pnpm)
│       └── app/
│           ├── (auth)/
│           ├── (dashboard)/
│           └── (marketing)/
├── packages/
│   └── widget/              # Embeddable JS chat widget
├── docs/
│   ├── architecture.md
│   └── ROADMAP.md
├── CLAUDE.md
└── LICENSE
```

**Rationale:** Shared tooling (CI, linting), atomic cross-component PRs, single source of truth. Python (uv) and Node (pnpm) are independent — no workspace manager needed across languages.

## Component Boundaries

### apps/web — Next.js Frontend (Vercel)

- Marketing site (/, /pricing, /docs)
- Auth pages via NextAuth.js (/login, /register)
- Dashboard (documents, API keys, billing, settings)
- Server components by default, client only when interactive
- Calls FastAPI backend — never touches MongoDB directly

### apps/api — FastAPI Backend (Railway)

- All AI/RAG logic: ingestion, retrieval, chat
- Document CRUD, conversation management
- Auth validation (API key lookup, session verification)
- Stripe webhook handling
- Adapted from coleam00/MongoDB-RAG-Agent `src/` modules

### packages/widget — Embeddable Chat Widget (CDN)

- Lightweight JS bundle (~50KB target)
- Script tag: `<script src="..." data-api-key="mrag_..." />`
- Renders chat bubble, sends queries directly to FastAPI
- No framework dependency — vanilla JS or Preact

## Data Flow

### Chat Query (widget to answer)

```
User types question
  → Widget POST /api/v1/chat {query, api_key}
    → FastAPI validates API key → extracts tenant_id
      → Pydantic AI agent receives query
        → Agent calls search_knowledge_base tool
          → asyncio.gather(
              vector_search(embedding, tenant_id, limit),
              text_search(query, tenant_id, limit)
            )
          → RRF merge (k=60) → top N chunks
        → Agent synthesizes answer from chunks
      → SSE stream response back to widget
    → Conversation saved to MongoDB
```

### Document Ingestion (dashboard to searchable chunks)

```
User uploads file via dashboard
  → Next.js POST /api/v1/documents (Supabase session)
    → FastAPI validates session → extracts tenant_id
      → BlobStore.put streams the upload → blob_uri
        (file://… in dev, supabase://mongorag-uploads/<tenant>/… in prod)
      → Insert documents row with status="pending"
      → Celery: ingest_document.delay(document_id, tenant_id, blob_uri, …)
    → Return document_id + status="pending" (immediate)

  Worker (separate Fly Machine):
    → _assert_tenant_owns_uri(blob_uri, tenant_id)
    → BlobStore.open → local tmpfile
    → Docling converts file → markdown (failures raise; no [Error:…] placeholders)
    → HybridChunker splits → semantic chunks (max_tokens=512)
    → Batch embed via OpenAI (text-embedding-3-small, 1536 dims, 100/batch)
    → MongoDB insert chunks
    → Flip documents.status="ready"
    → BlobStore.delete (24h Supabase lifecycle as safety net)
```

API and worker run as two separate processes (two Fly Machines from one Dockerfile, switched by `PROCESS_TYPE`); the Celery payload carries `blob_uri:` rather than a filesystem path. See `[[decision-blobstore-handoff]]` for the handoff rationale and `[[decision-deploy-fly-vercel]]` for the deploy topology.

**Design choices:**
- SSE streaming for chat (not WebSockets) — simpler, stateless, works through CDNs
- Content hashing for idempotent re-uploads
- Batch embedding (100 chunks/batch) to minimize API calls
- `tenant_id` injected at the API boundary, flows through every query

## Multi-Tenancy Strategy

**Model: Shared database, query-layer isolation.**

Every collection with tenant data includes `tenant_id`. Enforced at two levels:

1. **FastAPI dependency** — `get_current_tenant()` extracts `tenant_id` from auth context (session or API key). Every route that touches tenant data depends on it.
2. **MongoDB indexes** — Compound indexes include `tenant_id` first (e.g., `{tenant_id: 1, document_id: 1}`). Vector search uses `filter: {"tenant_id": tenant_id}`.

No DB-per-tenant. Simpler ops, single connection pool, easier backups. Tradeoff: noisy-neighbor risk at scale — mitigated by usage metering and rate limiting (Issue #11).

## Auth Strategy

Two mechanisms, two contexts:

| Context | Method | How it works |
|---------|--------|-------------|
| Dashboard | NextAuth.js sessions | Email/password → JWT → Next.js middleware validates → passes to FastAPI |
| Widget / Programmatic | API keys | `mrag_` prefixed → SHA256 hashed in DB → FastAPI header auth → tenant_id |

**API key design:**
- Format: `mrag_<32 random bytes hex>`
- Stored as SHA256 hash (never plaintext)
- Scoped to tenant, one tenant can have multiple keys
- Revocable instantly (delete hash)

**Not at MVP (YAGNI):**
- No OAuth providers (just email/password)
- No RBAC beyond tenant owner (Issue #29, Phase 10)

## Database Schema

### Collections

```
tenants
  _id, name, slug, plan, settings, created_at

users
  _id, email, password_hash, role, tenant_id, created_at

documents
  _id, title, source, content, content_hash, metadata, tenant_id, created_at

chunks
  _id, document_id, content, embedding[1536], chunk_index, metadata,
  token_count, tenant_id, created_at

api_keys
  _id, key_hash, prefix, name, tenant_id, created_at

conversations
  _id, messages[{role, content, timestamp}], tenant_id, created_at

subscriptions
  _id, tenant_id, stripe_customer_id, stripe_sub_id, plan (free|pro|enterprise),
  usage {queries, documents, chunks}, current_period_end, created_at
```

### Indexes

| Collection | Index | Type |
|-----------|-------|------|
| `chunks` | `embedding` | Atlas Vector Search (1536 dims, cosine) |
| `chunks` | `content` | Atlas Search (fuzzy, maxEdits: 2) |
| `chunks` | `{tenant_id, document_id}` | Compound |
| `api_keys` | `key_hash` | Unique |
| `users` | `email` | Unique |
| `documents` | `{tenant_id, content_hash}` | Compound unique |

Vector and text indexes must be created via Atlas UI or Atlas CLI — not programmatically via driver.

## Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent framework | Pydantic AI | Native Pydantic/FastAPI fit, ~3 deps vs LangChain's 50+, type-safe, proven in reference repo |
| Repo structure | Monorepo | Atomic PRs, shared CI, single source of truth |
| Tenancy model | Shared DB, query-layer isolation | Simpler ops, single connection pool |
| Embedding model | OpenAI text-embedding-3-small | 1536 dims, good quality/cost ratio, proven in reference repo |
| LLM provider | Pluggable (OpenAI, OpenRouter, Ollama, Gemini) | Reference repo's provider factory supports all |
| Search strategy | Hybrid RRF (semantic + text) | Better recall than either alone, works on free Atlas tier |
| Streaming | SSE (Server-Sent Events) | Simpler than WebSockets, stateless, CDN-friendly |
| Package managers | uv (Python), pnpm (Node) | Fast, modern, reliable |

## Deployment

### Primary: Vercel + Railway + MongoDB Atlas

```
                    ┌──────────────┐
                    │   Vercel     │
                    │  apps/web    │
                    │  Next.js     │
                    └──────┬───────┘
                           │
                    ┌──────┴───────┐
                    │   Railway    │
                    │  apps/api    │
                    │  FastAPI     │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │  MongoDB │ │  OpenAI  │ │  Stripe  │
        │  Atlas   │ │  API     │ │  API     │
        │  (Flex+) │ │          │ │          │
        └──────────┘ └──────────┘ └──────────┘
```

**Why:**
- **Vercel** — Native Next.js, zero-config, edge network, generous free tier
- **Railway** — Simple container hosting, auto-deploy, ~$5/mo hobby tier
- **Atlas Flex** — $8-30/mo, 5GB, Vector Search, no M10+ needed for MVP

### Environments

| Environment | Web | API | Atlas |
|---|---|---|---|
| Development | `localhost:3100` | `localhost:8100` | Free (M0) |
| Staging | Vercel preview | Railway staging | Flex |
| Production | Vercel production | Railway production | Flex → Dedicated |

### Alternative: Docker Compose (self-hosted)

For full control or lower cost at scale. MongoDB always runs on Atlas (Vector Search is Atlas-only) — Docker Compose covers application services only.

### CI/CD (Issue #3)

- GitHub Actions: lint + test on PR, auto-deploy on merge to main
- Vercel: auto-connected to repo
- Railway: auto-deploy from main branch

## Environment Variable Strategy

All configuration via environment variables, loaded through Pydantic Settings. Never hardcode secrets.

### Backend (apps/api/.env)

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `MONGODB_URI` | Yes | — | Atlas connection string |
| `MONGODB_DATABASE` | No | `rag_db` | Database name |
| `LLM_API_KEY` | Yes | — | LLM provider API key |
| `LLM_MODEL` | No | `anthropic/claude-haiku-4.5` | Model identifier |
| `LLM_BASE_URL` | No | `https://openrouter.ai/api/v1` | OpenAI-compatible endpoint |
| `EMBEDDING_API_KEY` | Yes | — | OpenAI API key for embeddings |
| `EMBEDDING_MODEL` | No | `text-embedding-3-small` | Embedding model |
| `STRIPE_SECRET_KEY` | Yes | — | Stripe API key |
| `STRIPE_WEBHOOK_SECRET` | Yes | — | Stripe webhook signing secret |
| `CORS_ORIGINS` | No | `http://localhost:3100` | Allowed CORS origins |

### Frontend (apps/web/.env.local)

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `NEXT_PUBLIC_API_URL` | Yes | — | FastAPI backend URL |
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | Yes | — | Stripe public key |
| `NEXTAUTH_SECRET` | Yes | — | NextAuth.js session secret |
| `NEXTAUTH_URL` | No | `http://localhost:3100` | NextAuth.js base URL |

### Conventions
- Pydantic Settings validates on startup — missing required vars crash immediately with clear error
- `.env.example` files in each app with dummy values
- No secrets in `.env.example` — only structure and comments
- Production secrets via Railway/Vercel environment variable UI

## MongoDB Atlas Vector Search — Capabilities and Limitations

### Capabilities
- **Vector Search (`$vectorSearch`)** — Cosine, dot product, or Euclidean similarity on up to 4096-dimension embeddings
- **Atlas Search (`$search`)** — Full-text search with fuzzy matching, autocomplete, facets
- **Filter in vector search** — Pre-filter on indexed fields (e.g., `tenant_id`) before ANN retrieval
- **Available on Free (M0)** — Vector Search works on all tiers including free
- **No code deployment** — Index definitions via Atlas UI or Atlas CLI, not driver API

### Limitations
- **Index creation** — Vector and search indexes cannot be created programmatically via MongoDB driver. Must use Atlas UI, Atlas CLI, or Atlas Admin API.
- **Free tier (M0)** — 512MB storage, ~100 ops/sec, 3 vector search indexes max, no continuous backup
- **Flex tier** — 5GB storage, 500 ops/sec, no private endpoints, no `$rankFusion` operator
- **`$rankFusion`** — Native RRF operator only available on M10+ dedicated clusters. Our implementation uses application-level RRF (from reference repo) which works on all tiers.
- **Index updates** — Vector index changes require re-indexing. Plan embedding dimension changes carefully.
- **numCandidates** — Must be set high enough for quality (we use `limit * 10`). Too low reduces recall; too high increases latency.
- **No real-time indexing** — Small delay (seconds) between insert and searchability. Not an issue for document ingestion, but worth noting.

### Our approach
Use application-level RRF (coleam00's implementation) instead of `$rankFusion` so we work on Free and Flex tiers. Upgrade to `$rankFusion` only if we move to M10+ dedicated.

## What We Reuse from coleam00/MongoDB-RAG-Agent

| Source File | Strategy | Adaptation |
|---|---|---|
| `src/tools.py` | Copy and adapt | Add `tenant_id` filter to all search pipelines |
| `src/ingestion/chunker.py` | Copy as-is | Tenant-agnostic, no changes |
| `src/ingestion/embedder.py` | Copy as-is | Tenant-agnostic, no changes |
| `src/ingestion/ingest.py` | Copy and adapt | Add `tenant_id`, `content_hash`, expose as route |
| `src/providers.py` | Copy as-is | Factory pattern works unchanged |
| `src/settings.py` | Copy and extend | Add SaaS config (Stripe, CORS, etc.) |
| `src/dependencies.py` | Rewrite | Replace with FastAPI `Depends()` pattern |
| `src/agent.py` | Copy and adapt | Wire to FastAPI route, pass `tenant_id` to tools |
| `src/prompts.py` | Copy and extend | Add tenant-customizable templates |
| `src/cli.py` | Drop | Replaced by HTTP API + widget |
| `examples/` | Drop | PostgreSQL reference, not relevant |
| `documents/` | Drop | Sample data |
| `test_scripts/` | Reference only | Inspiration for pytest suite |

### Preserved unchanged:
- RRF algorithm (k=60)
- Docling HybridChunker config (max_tokens=512)
- Embedding model (text-embedding-3-small, 1536 dims)
- Two-collection pattern (documents + chunks with `$lookup`)
