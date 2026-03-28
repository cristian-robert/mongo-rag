# System Architecture

## System Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Customer Website                            │
│                                                                     │
│  ┌───────────────────┐                                              │
│  │  <script> widget  │  Embeddable JS chat bubble                   │
│  └────────┬──────────┘                                              │
└───────────┼─────────────────────────────────────────────────────────┘
            │ HTTPS (API key in header)
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        FastAPI Service (apps/api)                    │
│                                                                     │
│  ┌──────────┐  ┌──────────────┐  ┌────────────┐  ┌──────────────┐  │
│  │ Chat API │  │ Ingestion API│  │ Document   │  │ Auth / Keys  │  │
│  │ /chat    │  │ /ingest      │  │ CRUD API   │  │ middleware   │  │
│  └────┬─────┘  └──────┬───────┘  └─────┬──────┘  └──────────────┘  │
│       │               │                │                            │
│  ┌────▼───────────────▼────────────────▼──────────────────────┐     │
│  │              Pydantic AI Agent Layer                        │     │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │     │
│  │  │ tools.py    │  │ providers.py │  │ prompts.py       │  │     │
│  │  │ hybrid_search│  │ LLM/embed   │  │ system prompts   │  │     │
│  │  └─────────────┘  └──────────────┘  └──────────────────┘  │     │
│  └────────────────────────────────────────────────────────────┘     │
│       │               │                                             │
│  ┌────▼───────────────▼────────────────────────────────────┐       │
│  │              Ingestion Pipeline                          │       │
│  │  Docling (PDF/Word/PPT/Excel/HTML/audio → markdown)     │       │
│  │  HybridChunker (semantic chunking)                      │       │
│  │  Batch Embedder (OpenAI text-embedding-3-small)         │       │
│  └─────────────────────────┬───────────────────────────────┘       │
└────────────────────────────┼────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      MongoDB Atlas                                  │
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────────┐   │
│  │documents │  │ chunks   │  │ tenants  │  │ conversations     │   │
│  │          │  │          │  │          │  │                   │   │
│  │title     │  │document_id│ │name      │  │tenant_id          │   │
│  │source    │  │content   │  │plan      │  │messages[]         │   │
│  │content   │  │embedding │  │api_keys[]│  │created_at         │   │
│  │tenant_id │  │tenant_id │  │users[]   │  │                   │   │
│  │metadata  │  │chunk_idx │  │settings  │  │                   │   │
│  └──────────┘  │metadata  │  └──────────┘  └───────────────────┘   │
│                │token_count│                                        │
│                └──────────┘  ┌──────────┐  ┌───────────────────┐   │
│                              │ users    │  │ subscriptions     │   │
│  Indexes:                    │          │  │                   │   │
│  - vector_index (chunks)     │email     │  │tenant_id          │   │
│  - text_index (chunks)       │tenant_id │  │stripe_customer_id │   │
│                              │role      │  │plan               │   │
│                              └──────────┘  └───────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    Next.js App (apps/web)                            │
│                                                                     │
│  ┌──────────┐  ┌──────────────┐  ┌────────────┐  ┌──────────────┐  │
│  │Dashboard │  │ Document     │  │ API Key    │  │ Billing      │  │
│  │ overview │  │ management   │  │ management │  │ (Stripe)     │  │
│  └──────────┘  └──────────────┘  └────────────┘  └──────────────┘  │
│                                                                     │
│  Auth: NextAuth.js (email/password, OAuth)                          │
│  BFF: API routes proxy to FastAPI                                   │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### User query (widget → answer)

```
1. User types question in widget
2. Widget sends POST /api/chat with API key header
3. Auth middleware validates API key → resolves tenant_id
4. Pydantic AI agent receives query
5. Agent calls hybrid_search tool:
   a. semantic_search: generate query embedding → $vectorSearch on chunks
   b. text_search: $search with fuzzy matching on chunks
   c. Both run concurrently via asyncio.gather
   d. Reciprocal Rank Fusion merges results: score = sum(1/(60+rank))
6. Agent receives top-K chunks as context
7. Agent generates answer grounded in retrieved chunks
8. Response streamed back via SSE
```

### Document ingestion

```
1. User uploads file via dashboard or API
2. Docling converts to markdown (PDF, Word, PPT, Excel, HTML, audio)
3. HybridChunker splits into semantic chunks (respects headings, paragraphs)
4. Batch embedder generates vectors via OpenAI API
5. Documents and chunks stored in MongoDB with tenant_id
6. Stable chunk IDs (SHA256 of content + source) enable idempotent upserts
```

## Decision: Monorepo

**Decision**: Monorepo with `apps/` and `packages/` structure.

**Rationale**:
- Single repo for all services simplifies CI/CD, code review, and dependency management
- Shared types and utilities between frontend and backend live in `packages/`
- Widget is a separate package with its own build pipeline
- Solo founder / small team — polyrepo overhead is not justified

**Structure**:
```
apps/api/        # FastAPI (Python, uv)
apps/web/        # Next.js (TypeScript, pnpm)
packages/widget/ # Embeddable JS bundle
docs/            # Architecture, ADRs
```

## Decision: Pydantic AI for Agent Orchestration

**Decision**: Pydantic AI (not LangChain, not LlamaIndex).

**Rationale**:
- Native Pydantic integration with FastAPI — shared type system, no serialization gaps
- Lightweight: ~3 dependencies vs LangChain's 50+
- First-class type safety throughout the stack
- Proven in the reference repo (coleam00/MongoDB-RAG-Agent)
- RAG pipeline is straightforward: retrieve → generate. LangChain's abstractions don't pay off here.
- Tool calling pattern maps directly to our search functions

## Component Boundaries

### Next.js App (`apps/web`)

**Responsibility**: Marketing site, dashboard, auth pages, API routes (BFF pattern).

- Server-rendered pages with Next.js App Router
- NextAuth.js handles user sessions (email/password + OAuth providers)
- API routes proxy dashboard requests to FastAPI backend
- No direct MongoDB access — all data flows through FastAPI
- Manages Stripe checkout and billing portal redirects

### FastAPI Service (`apps/api`)

**Responsibility**: RAG ingestion, retrieval, chat, document CRUD.

Built by wrapping and extending coleam00's `src/` modules:

| Module | Source | Purpose |
|--------|--------|---------|
| `tools.py` | Reference repo | Hybrid RRF search (semantic + text + fusion) |
| `ingestion/` | Reference repo | Docling chunker + batch embedder |
| `providers.py` | Reference repo | Pluggable LLM/embedding providers |
| `agent.py` | Reference repo | Pydantic AI agent with tool calling |
| `settings.py` | Reference repo | Pydantic Settings configuration |
| `dependencies.py` | Reference repo | MongoDB connection + agent deps |

**Added on top**:
- FastAPI HTTP endpoints (the reference repo is CLI-only)
- Tenant isolation middleware
- API key authentication
- Conversation history storage
- SSE streaming responses
- Document CRUD operations
- Stable chunk IDs for idempotent upserts

### Embeddable Widget (`packages/widget`)

**Responsibility**: Lightweight JS bundle customers embed via `<script>` tag.

- Vanilla JS, no framework dependency
- Renders a chat bubble and conversation panel
- Communicates with FastAPI via API key in headers
- Configurable: colors, position, welcome message, bot name
- Self-contained — single `<script src="...">` tag

## Multi-Tenancy Strategy

**Approach**: Shared database, tenant ID on every document.

Every collection document includes a `tenant_id` field. Every query filters by `tenant_id`. This is enforced at the application query layer.

**Rules**:
1. `tenant_id` is derived from the authenticated session or API key — never from client input
2. Every MongoDB query must include `tenant_id` in the filter
3. Ingestion pipeline stamps `tenant_id` on documents and chunks at write time
4. Search pipelines add `$match: {tenant_id}` stage after `$vectorSearch` / `$search`
5. No cross-tenant data access is possible through the API

**Why shared database (not database-per-tenant)**:
- Simpler ops for a solo founder / small team
- MongoDB Atlas pricing is per-cluster, not per-database
- Vector Search indexes are per-collection — separate databases would multiply index management
- Tenant isolation at the query layer is sufficient for this scale

## Authentication Strategy

### Dashboard users (apps/web)

- **NextAuth.js** with email/password credentials provider
- OAuth providers (Google, GitHub) as optional additions
- Session stored server-side (MongoDB adapter for NextAuth)
- Protected routes via Next.js middleware

### API / Widget access (apps/api)

- **API keys** generated per tenant
- Keys are prefixed (`mrag_`) and stored as SHA256 hashes in MongoDB
- Widget includes API key in `X-API-Key` header
- FastAPI dependency extracts and validates key, resolves `tenant_id`
- Rate limiting applied per API key

### Flow

```
Dashboard login:
  Browser → NextAuth.js → session cookie → API routes → FastAPI (internal, trusted)

Widget / programmatic:
  Widget → X-API-Key header → FastAPI auth middleware → tenant_id resolved
```

## Database Schema

Extends the reference repo's `documents` + `chunks` collections with multi-tenant and SaaS collections.

### Core RAG collections (from coleam00/MongoDB-RAG-Agent)

**documents**
```json
{
  "_id": "ObjectId",
  "tenant_id": "ObjectId",
  "title": "string",
  "source": "string",
  "content": "string",
  "content_hash": "string (SHA256)",
  "metadata": {},
  "version": "int",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**chunks**
```json
{
  "_id": "string (SHA256 of content+source — stable ID)",
  "document_id": "ObjectId",
  "tenant_id": "ObjectId",
  "content": "string",
  "embedding": "[float] (1536 dims)",
  "chunk_index": "int",
  "metadata": {},
  "token_count": "int",
  "created_at": "datetime"
}
```

### Search indexes (created in Atlas UI)

- **vector_index** on `chunks.embedding` — `numDimensions: 1536, similarity: cosine`
- **text_index** on `chunks.content` — Atlas Search with fuzzy matching

### SaaS collections

**tenants**
```json
{
  "_id": "ObjectId",
  "name": "string",
  "slug": "string (unique)",
  "plan": "free | starter | pro | enterprise",
  "settings": {
    "bot_name": "string",
    "welcome_message": "string",
    "theme": {}
  },
  "created_at": "datetime"
}
```

**users**
```json
{
  "_id": "ObjectId",
  "tenant_id": "ObjectId",
  "email": "string (unique)",
  "password_hash": "string",
  "role": "owner | admin | member",
  "created_at": "datetime"
}
```

**api_keys**
```json
{
  "_id": "ObjectId",
  "tenant_id": "ObjectId",
  "key_hash": "string (SHA256)",
  "prefix": "string (mrag_xxxx — for identification)",
  "name": "string",
  "last_used_at": "datetime",
  "created_at": "datetime",
  "revoked_at": "datetime | null"
}
```

**conversations**
```json
{
  "_id": "ObjectId",
  "tenant_id": "ObjectId",
  "api_key_id": "ObjectId",
  "messages": [
    {
      "role": "user | assistant",
      "content": "string",
      "sources": ["chunk_id"],
      "timestamp": "datetime"
    }
  ],
  "created_at": "datetime"
}
```

**subscriptions**
```json
{
  "_id": "ObjectId",
  "tenant_id": "ObjectId",
  "stripe_customer_id": "string",
  "stripe_subscription_id": "string",
  "plan": "free | starter | pro | enterprise",
  "status": "active | canceled | past_due",
  "current_period_end": "datetime",
  "usage": {
    "queries_this_month": "int",
    "documents_stored": "int",
    "storage_bytes": "int"
  }
}
```

## Deployment Target

### Primary: Docker Compose (self-hosted / VPS)

```
docker-compose.yml
├── api      (FastAPI, Python 3.10+, uvicorn)
├── web      (Next.js, Node 20+, standalone output)
└── nginx    (reverse proxy, SSL termination)
```

MongoDB Atlas is always external (managed service) — never self-hosted.

### Alternative: Vercel + Railway/Fly.io

- `apps/web` → Vercel (free tier works for MVP)
- `apps/api` → Railway or Fly.io (Python runtime)
- Good for quick iteration, but Docker Compose provides more control

### Environment variable strategy

- `.env` files for local development (git-ignored)
- `.env.example` checked into repo with placeholder values
- Production secrets via platform-native secret management (Railway secrets, Fly.io secrets, Docker secrets)
- Never commit real credentials

## What We Reuse from coleam00/MongoDB-RAG-Agent

| Component | File | What it does | How we extend it |
|-----------|------|-------------|-----------------|
| Hybrid RRF search | `src/tools.py` | Concurrent vector + text search with Reciprocal Rank Fusion | Add `tenant_id` filter, expose via HTTP |
| Document ingestion | `src/ingestion/` | Docling HybridChunker + batch embedder (PDF, Word, PPT, Excel, HTML, MD, audio) | Add stable chunk IDs, tenant isolation, HTTP upload endpoint |
| Pluggable providers | `src/providers.py` | OpenAI, OpenRouter, Ollama, Gemini support via OpenAI-compatible API | Keep as-is, configure per environment |
| Agent pattern | `src/agent.py` | Pydantic AI agent with tool calling | Add conversation history, streaming SSE |
| Configuration | `src/settings.py` | Pydantic Settings from `.env` | Add SaaS-specific settings (Stripe, auth) |
| Dependencies | `src/dependencies.py` | MongoDB + OpenAI client management | Add connection pooling for multi-tenant |
| MongoDB indexes | Collections | `vector_index` + `text_index` definitions | Same indexes, add compound indexes with `tenant_id` |

## Sub-tasks Status

- [x] Evaluate Pydantic AI vs LangChain → **Decided: Pydantic AI**
- [x] Document what to reuse from coleam00/MongoDB-RAG-Agent
- [ ] Fork/vendor coleam00/MongoDB-RAG-Agent code into `apps/api/`
- [ ] Research MongoDB Atlas Vector Search capabilities and limitations
- [ ] Decide on embedding model → **Recommendation: OpenAI `text-embedding-3-small`** (1536 dims, good cost/quality tradeoff, proven in reference repo)
- [ ] Decide on LLM provider → **Recommendation: Pluggable** (default OpenRouter with Claude Haiku, swap via env vars)
- [ ] Document environment variable strategy → See Deployment section above
