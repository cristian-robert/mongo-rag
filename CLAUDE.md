# CLAUDE.md

## Project Overview

MongoRAG is a multi-tenant AI chatbot SaaS. Customers sign up, upload documents, get an embeddable script tag, and install a chatbot on their website that answers questions grounded in their own data.

Built on top of [coleam00/MongoDB-RAG-Agent](https://github.com/coleam00/MongoDB-RAG-Agent) — a working RAG agent with hybrid search (RRF), Docling-based ingestion, pluggable LLM providers, and MongoDB Atlas Vector Search.

## Architecture

- **`apps/web`** — Next.js frontend (dashboard, marketing, auth via NextAuth.js)
- **`apps/api`** — FastAPI backend (RAG ingestion, retrieval, chat, document CRUD)
- **`packages/widget`** — Embeddable JS chat widget for customer websites
- **MongoDB Atlas** — Vector Search + full-text search with Reciprocal Rank Fusion
- **Pydantic AI** — Agent orchestration (not LangChain)
- **Stripe** — Subscriptions and billing

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js, TypeScript |
| Backend | FastAPI, Python 3.10+ |
| Agent | Pydantic AI with tool calling |
| Database | MongoDB Atlas (Vector Search + Atlas Search) |
| Embeddings | OpenAI text-embedding-3-small (1536 dims) |
| LLM | Pluggable — OpenAI, OpenRouter, Ollama, Gemini |
| Ingestion | Docling HybridChunker + batch embedder |
| Auth | NextAuth.js (dashboard), API keys (widget/programmatic) |
| Billing | Stripe |
| Package manager | uv (Python), pnpm (Node) |

## Repository Structure

```
mongo-rag/
├── apps/
│   ├── api/                 # FastAPI backend
│   │   └── src/
│   │       ├── agent.py     # Pydantic AI agent with search tools
│   │       ├── tools.py     # Hybrid RRF search (semantic + text + fusion)
│   │       ├── providers.py # Pluggable LLM/embedding providers
│   │       ├── settings.py  # Pydantic Settings configuration
│   │       ├── dependencies.py
│   │       ├── prompts.py
│   │       └── ingestion/
│   │           ├── ingest.py    # MongoDB ingestion pipeline
│   │           ├── chunker.py   # Docling HybridChunker wrapper
│   │           └── embedder.py  # Batch embedding generation
│   └── web/                 # Next.js frontend
├── packages/
│   └── widget/              # Embeddable chat widget
├── docs/
│   ├── architecture.md
│   └── ROADMAP.md
├── CLAUDE.md
└── LICENSE
```

## Key Patterns from Reference Repo

### Search: Three-tier hybrid search

1. **Semantic search** — `$vectorSearch` on embeddings
2. **Text search** — `$search` with fuzzy matching (`maxEdits: 2, prefixLength: 3`)
3. **Hybrid (RRF)** — Runs both concurrently via `asyncio.gather`, merges with `RRF_score = sum(1 / (60 + rank))`

### Ingestion pipeline

1. Read document (Docling converts PDF/Word/PPT/Excel/HTML/audio to markdown)
2. Chunk with Docling HybridChunker (semantic boundaries, heading context)
3. Batch embed via OpenAI API
4. Store in MongoDB: `documents` collection + `chunks` collection with `$lookup` joins

### MongoDB collections

- `documents` — `{title, source, content, metadata, created_at}`
- `chunks` — `{document_id, content, embedding, chunk_index, metadata, token_count, created_at}`
- Indexes: `vector_index` on `chunks.embedding`, `text_index` on `chunks.content`

### What we add on top

- `tenant_id` on every query and collection document
- FastAPI HTTP API (reference repo is CLI-only)
- Auth, billing, dashboard, widget
- Conversation history, streaming SSE
- Stable chunk IDs (SHA256) for idempotent upserts

## Multi-Tenancy

Every database query must include `tenant_id`. This is enforced at the query layer, not the database layer. Never trust tenant identity from client input alone — derive it from the authenticated session or API key.

## Configuration

All secrets and configuration load from environment variables via Pydantic Settings. Never hardcode secrets. See `.env.example` for the full list.

Key variables:
- `MONGODB_URI` — Atlas connection string
- `LLM_API_KEY` — LLM provider API key
- `EMBEDDING_API_KEY` — Embedding provider API key
- `LLM_MODEL` — Model identifier (e.g., `anthropic/claude-haiku-4.5`)
- `EMBEDDING_MODEL` — Embedding model (default: `text-embedding-3-small`)

## Development Commands

```bash
# Python backend (apps/api)
uv sync                          # Install dependencies
uv run python -m src.cli         # Run CLI agent
uv run python -m src.ingestion.ingest  # Run document ingestion
uv run pytest                    # Run tests
uv run pytest -m unit            # Unit tests only
uv run pytest -m integration     # Integration tests only
uv run ruff check .              # Lint
uv run black --check .           # Format check

# Next.js frontend (apps/web)
pnpm install                     # Install dependencies
pnpm dev                         # Dev server
pnpm build                       # Production build
pnpm lint                        # Lint
pnpm test                        # Tests
```

## Code Style

### Python (backend)

- Type annotations on all function signatures and return types
- Pydantic models for all data structures (not raw dicts)
- Async for all I/O (MongoDB, HTTP, embedding calls)
- Use `asyncio.gather` for concurrent independent operations
- Pydantic Settings for configuration, not raw `os.getenv`
- Structured logging with context (not print statements)
- Handle MongoDB-specific exceptions: `ConnectionFailure`, `OperationFailure`, `ServerSelectionTimeoutError`
- Embeddings are Python lists of floats, never JSON strings

### TypeScript (frontend)

- Strict TypeScript, no `any` types
- Server components by default, client components only when needed
- No AI-generated placeholder content or decorative UI
- Clean, functional components

### General

- No premature abstractions — three similar lines beat a wrapper nobody needs
- No dead code, no commented-out code, no `_unused` variables
- Tests mirror the source tree structure
- Validate at system boundaries (user input, external APIs), trust internal code

## Common Pitfalls

- **Embedding format**: MongoDB stores embeddings as native arrays (Python lists). Never serialize to JSON strings.
- **Vector indexes**: Cannot be created programmatically — must use Atlas UI or Atlas CLI.
- **Async discipline**: Every MongoDB and API call must be awaited. Missing `await` causes silent failures.
- **Tenant isolation**: Every query must filter by `tenant_id`. This is the most critical security boundary.
- **Atlas tiers**: Free (M0) supports Vector Search but with constraints (0.5GB, 100 ops/sec). Plan accordingly.
