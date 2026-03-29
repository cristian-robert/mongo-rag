# MongoRAG Architecture Index

## Backend Modules (apps/api/src/)
- agent.py — Pydantic AI agent with search tools, conversation management
- tools.py — Hybrid RRF search (semantic + text + fusion), MongoDB queries
- providers.py — Pluggable LLM/embedding providers (OpenAI, OpenRouter, Ollama, Gemini)
- settings.py — Pydantic Settings configuration (env vars)
- dependencies.py — FastAPI dependency injection (DB connections, auth, tenant context)
- prompts.py — System prompt templates, versioned prompt management
- ingestion/ — Document ingestion pipeline (chunker, embedder, ingest)

## Backend API Routes (apps/api/src/routes/)
- /api/v1/chat — Chat endpoint (streaming SSE + sync)
- /api/v1/documents — Document CRUD (upload, list, update, delete)
- /api/v1/ingest — Document ingestion trigger
- /api/v1/tenants — Tenant management
- /api/v1/auth — Authentication endpoints
- /api/v1/keys — API key management
- /api/v1/billing — Stripe subscription management

## Frontend Route Groups (apps/web/app/)
- (auth) — /login, /register, /forgot-password, /reset-password
- (dashboard) — /dashboard, /documents, /api-keys, /settings, /billing
- (marketing) — /, /pricing, /docs

## Frontend Components (apps/web/components/)
- ui/ — shadcn/ui primitives
- dashboard/ — Dashboard layout, navigation, overview widgets
- documents/ — Upload, list, manage documents
- chat/ — Chat widget preview, conversation history
- billing/ — Plan cards, usage meters, checkout

## Widget (packages/widget/)
- Lightweight embeddable JS chat bubble
- Script tag: `<script src="..." data-api-key="mrag_..." />`
- Communicates with /api/v1/chat via API key auth

## MongoDB Collections
- `documents` — {title, source, content, content_hash, metadata, tenant_id}
- `chunks` — {document_id, content, embedding[1536], chunk_index, metadata, token_count, tenant_id}
- `tenants` — {name, slug, plan, settings}
- `users` — {email, password_hash, role, tenant_id}
- `api_keys` — {key_hash, prefix, name, tenant_id}
- `conversations` — {messages[], tenant_id}
- `subscriptions` — {stripe_customer_id, plan, usage}

## Indexes
- `vector_index` on `chunks.embedding` (numDimensions: 1536, cosine similarity)
- `text_index` on `chunks.content` (Atlas Search with fuzzy matching)
- Unique index on `api_keys.key_hash`
- Compound index on `chunks.{tenant_id, document_id}`

## Key Decisions
- Pydantic AI over LangChain (lightweight, native FastAPI fit)
- Shared database with query-layer tenant isolation (not DB-per-tenant)
- API key auth for widget (mrag_* prefix, SHA256 hashed)
- NextAuth.js for dashboard auth
- uv for Python, pnpm for Node
