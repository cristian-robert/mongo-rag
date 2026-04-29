# MongoRAG Development Instructions

## Project Overview

Multi-tenant AI chatbot SaaS powered by RAG. Customers sign up, upload documents, get an embeddable script tag, and install a chatbot on their website that answers questions grounded in their own data.

Built on top of [coleam00/MongoDB-RAG-Agent](https://github.com/coleam00/MongoDB-RAG-Agent) — a working RAG agent with hybrid search (RRF), Docling-based ingestion, pluggable LLM providers, and MongoDB Atlas Vector Search.

This repo also runs the **AIDevelopmentFramework** (PIV+E loop) for development discipline. See "Pipeline Commands" below.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js (App Router), TypeScript |
| Backend | FastAPI, Python 3.10+ |
| Agent | Pydantic AI with tool calling |
| Database | MongoDB Atlas (Vector Search + Atlas Search) |
| Embeddings | OpenAI text-embedding-3-small (1536 dims) |
| LLM | Pluggable — OpenAI, OpenRouter, Ollama, Gemini |
| Ingestion | Docling HybridChunker + batch embedder |
| Auth | Supabase Auth (email/password via @supabase/ssr) for dashboard; API keys (widget/programmatic) |
| Billing | Stripe |
| Package manager | uv (Python), pnpm (Node) |

## Core Principles

1. **TYPE SAFETY** — Type annotations on all Python functions. Pydantic models for all data. Strict TypeScript, no `any`.
2. **KISS** — Simple, readable solutions. No premature abstractions.
3. **YAGNI** — MVP first, enhancements later. Build only what's needed now.
4. **TENANT ISOLATION** — Every database query must include `tenant_id`. This is the most critical security boundary.
5. **ASYNC EVERYTHING** — All I/O (MongoDB, HTTP, embedding calls) must be async with proper await.
6. **Context is precious** — manage it deliberately; recommend context resets for complex work.
7. **Plans are artifacts** — survive session boundaries; pass the "no prior knowledge" test.
8. **The system self-improves** — every AI mistake becomes a rule, pattern, or guardrail (`/evolve`).

## Architecture

```text
mongo-rag/
├── apps/
│   ├── api/                 # FastAPI backend (Python)
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
│       └── app/             # App Router pages
├── packages/
│   └── widget/              # Embeddable JS chat widget
├── docs/
│   ├── architecture.md
│   └── ROADMAP.md
├── .obsidian/               # Knowledge Base (raw + wiki + _search)
├── .claude/                 # Framework rules, agents, references
├── cli/                     # KB CLI tool (kb-search.js)
├── CLAUDE.md
└── LICENSE
```

---

## Development Workflow

### GitHub Issue-Driven — MANDATORY

**EVERY task MUST start from a GitHub issue.** Workflow:

1. Require a GitHub issue — ask if none provided
2. Read with `gh issue view <number>`
3. Create branch: `<type>/<description>` (feature/, fix/, refactor/, chore/)
4. Work on branch, commit with `/commit`
5. Create PR with `/commit-push-pr`, link issue (`Closes #<number>`)
6. **STOP and wait** — never assume PR is merged
7. Address review comments → push fixes → wait again
8. After merge confirmation → clean up branch, run `/clear`

**Rules:** Never work without an issue. Never assume merge. Never commit to `main` directly.

### Architect-Agent Protocol

**When:** BEFORE/AFTER structural changes (modules, endpoints, routes, DB collections, components).
**How:** Agent tool → `subagent_type: "general-purpose"`. Prompt: `You are the architect-agent for the MongoRAG project. Read .claude/agents/architect-agent/AGENT.md for your instructions. Then respond to this query:`
**Queries:** `RETRIEVE domain:<area>`, `IMPACT`, `RECORD domain:<area>`, `PATTERN`
**Models:** `haiku` for RETRIEVE/PATTERN, `sonnet` for IMPACT/RECORD

### Tester-Agent Protocol (Web Only)

**When:** After web UI changes, before claiming web frontend work is done.
**How:** Agent tool → `subagent_type: "general-purpose"`, `model: "sonnet"`. Prompt: `You are the tester-agent for the MongoRAG project. Read .claude/agents/tester-agent/AGENT.md for your instructions. Then run this test:`
**Queries:** `VERIFY page:<path> Checks: <list>` or `FLOW: <scenario> Steps: 1. ... 2. ...`

---

## Pipeline Commands (PIV+E)

Plan → Implement → Validate → Evolve. Use these for non-trivial work.

| Command | Phase | Purpose |
|---------|-------|---------|
| `/start` | Router | Detects scope level, routes to correct pipeline |
| `/prime` | Plan | Loads codebase context into session |
| `/create-prd` | Plan | Generates PRD from idea (includes brainstorming) |
| `/plan-project` | Plan | Decomposes PRD into GitHub milestones + issues |
| `/plan-feature` | Plan | Creates detailed implementation plan for a feature |
| `/execute` | Implement | Executes plan with TDD, domain skills, parallel agents |
| `/validate` | Validate | Runs verification, testing agents, code review |
| `/ship` | Validate | Commits, pushes, creates PR, finishes branch |
| `/evolve` | Evolve | Updates rules and knowledge base from learnings |
| `/setup` | Utility | Checks installed plugins/skills, reports health |

### Scope Levels

- **L0 (Project):** /brainstorm → /create-prd → /plan-project → per-issue L2
- **L1 (Feature):** /brainstorm → /plan-feature → creates issue(s) → per-issue L2
- **L2 (Issue):** gh issue view → /prime → /writing-plans → /execute → /validate → /ship
- **L3 (Bug):** gh issue view → /prime → /systematic-debugging → fix → /validate → /ship

### Mode Selection

- **Superpowers Mode:** brainstorm → plan → TDD → execute (subagent-driven) → /validate (QA + security + visual + review) → ship → evolve
- **Standard Mode:** plan → implement → validate → ship

### Verification Standard

Both modes MUST run `/validate` before `/ship`. The superpowers `verification-before-completion` skill is NOT a substitute for `/validate`. The superpowers `requesting-code-review` skill is NOT a substitute for `/validate` Phase 5.

### Code Review Layers

| Layer | Command | What it checks |
|-------|---------|----------------|
| Superpowers Code Review | `/validate` Phase 5 | Implementation defects, plan adherence, security, edge cases |
| Codex Adversarial Review | `/ship` Step 1.6 | Design choices, tradeoffs, assumptions, alternatives (optional) |

---

## Setup & Commands

```bash
# Python backend (apps/api)
uv sync                          # Install dependencies
uv run uvicorn src.main:app --reload --port 8100  # Dev server (port 8100)
uv run python -m src.cli         # Run CLI agent
uv run python -m src.ingestion.ingest  # Run document ingestion
uv run pytest                    # Run tests
uv run pytest -m unit            # Unit tests only
uv run pytest -m integration     # Integration tests only
uv run ruff check .              # Lint
uv run ruff format --check .     # Format check

# Next.js frontend (apps/web)
pnpm install                     # Install dependencies
pnpm dev                         # Dev server (port 3100)
pnpm build                       # Production build
pnpm lint                        # Lint
pnpm test                        # Tests
```

## Environment Variables

- **Backend** (`apps/api/.env`): `MONGODB_URI`, `LLM_API_KEY`, `EMBEDDING_API_KEY`, `LLM_MODEL`, `EMBEDDING_MODEL`, `STRIPE_SECRET_KEY`
- **Frontend** (`apps/web/.env.local`): `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_APP_URL`, `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`

## Code Patterns & Conventions

> Read `.claude/references/code-patterns.md` when writing, reviewing, or debugging code.

## Key Patterns from Reference Repo

### Search: Three-tier hybrid search

1. **Semantic search** — `$vectorSearch` on embeddings
2. **Text search** — `$search` with fuzzy matching (`maxEdits: 2, prefixLength: 3`)
3. **Hybrid (RRF)** — Runs both concurrently via `asyncio.gather`, merges with `RRF_score = sum(1 / (60 + rank))`

### Ingestion pipeline

1. Read document (Docling converts PDF/Word/PPT/Excel/HTML/audio to markdown)
2. Chunk with Docling HybridChunker (semantic boundaries, heading context)
3. Batch embed via OpenAI API
4. Store in MongoDB: `documents` collection + `chunks` collection

### MongoDB Collections

- `documents` — `{title, source, content, content_hash, metadata, tenant_id, created_at}`
- `chunks` — `{document_id, content, embedding[1536], chunk_index, metadata, token_count, tenant_id, created_at}`
- `tenants` — `{name, slug, plan, settings}`
- `users` — `{email, password_hash, role, tenant_id}`
- `api_keys` — `{key_hash, prefix, name, tenant_id}`
- `conversations` — `{messages[], tenant_id}`
- `subscriptions` — `{stripe_customer_id, plan, usage}`
- **Indexes:** `vector_index` on `chunks.embedding`, `text_index` on `chunks.content`

## Multi-Tenancy

Every database query must include `tenant_id`. Enforced at the query layer, not the database layer. Never trust tenant identity from client input alone — derive from authenticated session or API key.

## Configuration

All secrets and configuration load from environment variables via Pydantic Settings. Never hardcode secrets. Key variables:
- `MONGODB_URI` — Atlas connection string
- `LLM_API_KEY` / `EMBEDDING_API_KEY` — Provider API keys
- `LLM_MODEL` — Model identifier (e.g., `anthropic/claude-haiku-4.5`)
- `EMBEDDING_MODEL` — Embedding model (default: `text-embedding-3-small`)

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
- Clean, functional components
- React Hook Form + Zod for forms

### General

- No premature abstractions — three similar lines beat a wrapper nobody needs
- No dead code, no commented-out code, no `_unused` variables
- Tests mirror the source tree structure
- Validate at system boundaries (user input, external APIs), trust internal code

## Common Pitfalls

- **Embedding format**: MongoDB stores embeddings as native arrays (Python lists). Never serialize to JSON strings.
- **Vector indexes**: Cannot be created programmatically — must use Atlas UI or Atlas CLI.
- **Async discipline**: Every MongoDB and API call must be awaited. Missing `await` causes silent failures.
- **Tenant isolation**: Every query must filter by `tenant_id`. Most critical security boundary.
- **Atlas tiers**: Free (M0) supports Vector Search but with constraints (0.5GB, 100 ops/sec).

---

## Knowledge Base

Path: .obsidian/

Unified LLM knowledge base inspired by [Karpathy's LLM Knowledge Bases](https://x.com/karpathy) workflow. Raw sources + compiled wiki articles live together as a flat Obsidian-compatible vault.

**Structure:**

```
.obsidian/
├── raw/                 # Ingested source material (read-only)
│   └── _manifest.md     # Index of all raw sources with status
├── wiki/                # Unified wiki — flat .md files with frontmatter
│   ├── _index.md        # Master index grouped by type
│   └── _tags.md         # Tag registry with article counts
└── _search/
    ├── index.json       # TF-IDF search index (auto-generated)
    └── stats.md         # KB health metrics
```

**KB Commands:**

- `/kb ingest <source>` — ingest URL, file, repo, or session learnings → raw/ + wiki stub
- `/kb compile` — expand stubs, cross-link, extract concepts, health check
- `/kb search <query>` — TF-IDF search across wiki
- `/kb ask <question>` — Q&A against wiki, answer filed back as new article

**Pipeline integration:**

- `/prime` reads wiki index + auto-searches for task-relevant articles
- `/execute` searches wiki before each task for relevant context
- `/ship` updates feature articles with implementation details, creates decision articles
- `/evolve` captures session learnings as raw + stub wiki articles

Rebuild indexes after manual edits: `KB_PATH=.obsidian node cli/kb-search.js index`

---

## Skills & Plugins

50+ specialized skills, 2 subagents (`architect-agent`, `tester-agent`), and MCP servers (context7, shadcn). Full trigger table in `~/.claude/CLAUDE.md`.

**Technology-specific skills used in this project:**
- `/fastapi-python` — FastAPI patterns, async endpoints, dependency injection
- `/mongodb` — MongoDB queries, aggregation pipelines, indexes
- `/mongodb-development` — MongoDB development best practices
- `/pydantic-ai-agent-creation` — Pydantic AI agent patterns
- `/pydantic-ai-tool-system` — Pydantic AI tool definitions
- `/stripe-best-practices` — Stripe integration best practices (official)
- `/nextjs-app-router-patterns` — Next.js App Router, server components
- `/vercel-react-best-practices` — React/Next.js performance optimization
- `/shadcn-ui` — shadcn/ui component library patterns

**Testing overrides:**
- Web UI → `tester-agent` (not `/agent-browser`)

**Domain-specific skill recipes load automatically from `.claude/rules/`:**
- `backend.md` — FastAPI/Pydantic/MongoDB/Pydantic AI/Stripe (loads for `apps/api/**`)
- `frontend.md` — Design skill gate, shadcn MCP, Next.js (loads for `apps/web/**`)
- `database.md`, `security.md`, `testing.md`, `mobile.md`, `knowledge-base.md` — load by file path / topic

### Development Mode Selection — ASK EVERY TIME

For non-trivial tasks, ask before starting:

> 1. **Superpowers Mode** — Full discipline (brainstorming, TDD, plans, verification, code review)
> 2. **Standard Mode** — Domain skills only, faster iteration

Skip for trivial changes. Reuse previous choice this session.

### Cross-Cutting Skill Recipes

**Full-stack feature:** `architect-agent` IMPACT → `/feature-dev` → stack domain skills from rules
**Bug fixing:** Superpowers: `/superpowers:systematic-debugging` first. Standard: investigate + domain skills.
**Research:** `/research` (multi-source), `/search` (quick lookup), `/extract` (URL content), `/crawl` (download sites)
**Library APIs:** `context7` MCP (`resolve-library-id` → `query-docs`) — verify before writing code
**Claiming done:** Load `/superpowers:verification-before-completion`. Run tests. Web: `tester-agent`. Run `/simplify` before committing.

### Superpowers Pipeline

`/brainstorming` → `/writing-plans` → `/test-driven-development` → domain skills → `/executing-plans` → `/verification-before-completion` → `/finishing-a-development-branch`

Parallel: `/dispatching-parallel-agents` or `/subagent-driven-development`. Debug: `/systematic-debugging`.

---

## QA Tools

Default QA test tools by domain. Override per-project by editing this section.

| Domain | Tool |
|--------|------|
| Web E2E | Playwright (via `tester-agent`) |
| API E2E | pytest + httpx (`uv run pytest -m integration`) |

## Output Compaction

State: off

Controls the `.claude/hooks/output-compact.sh` Stop hook. Defaults to OFF — flip to `on` to enable. Read the rules in `.claude/references/output-compaction.md` first. Override per-session with `CLAUDE_OUTPUT_COMPACT=on|off`.

## External Dependencies

Run `/setup` to check what's installed. See `docs/plugin-install-guide.md` for full list.
