# Monorepo Setup Design — Issue #2

## Summary

Initialize the monorepo with Next.js frontend, FastAPI backend (with all reference app code), embeddable widget scaffold, Docker Compose, and Makefile. This creates the skeleton that all feature work builds into.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| FastAPI structure | Layered (`routers/`, `models/`, `services/`, `core/`) | Conventional FastAPI layout, scales with the project |
| Reference code | Copy all into layered structure | Working code from day one, reorganized to fit layered layout |
| Next.js setup | `create-next-app` + shadcn/ui | Standard setup, shadcn/ui needed for dashboard (Phase 5) |
| Widget bundler | esbuild | Minimal, fast, right-sized for a single JS bundle |
| Docker Compose | `web` + `api` only (no local MongoDB) | Always use Atlas — even M0 free tier has Vector Search |
| Root scripts | Makefile | Clean, self-documenting, works for both Python and Node |

## Monorepo Structure

```
mongo-rag/
├── apps/
│   ├── api/                          # FastAPI backend (Python, uv)
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   ├── main.py               # App factory, CORS, lifespan
│   │   │   ├── routers/
│   │   │   │   ├── __init__.py
│   │   │   │   └── health.py         # GET /health
│   │   │   ├── models/
│   │   │   │   ├── __init__.py
│   │   │   │   └── search.py         # SearchResult (from tools.py)
│   │   │   ├── services/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── agent.py          # Pydantic AI agent
│   │   │   │   ├── search.py         # semantic/text/hybrid/RRF
│   │   │   │   └── ingestion/
│   │   │   │       ├── __init__.py
│   │   │   │       ├── ingest.py
│   │   │   │       ├── chunker.py
│   │   │   │       └── embedder.py
│   │   │   ├── core/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── settings.py
│   │   │   │   ├── dependencies.py
│   │   │   │   ├── providers.py
│   │   │   │   └── prompts.py
│   │   │   └── cli.py                # CLI agent (kept for dev use)
│   │   ├── tests/
│   │   │   └── __init__.py
│   │   ├── pyproject.toml
│   │   ├── Dockerfile
│   │   └── .env.example
│   └── web/                          # Next.js 14+ App Router
│       ├── app/
│       ├── components/
│       ├── lib/
│       ├── Dockerfile
│       ├── .env.example
│       └── ...                       # Standard create-next-app + shadcn/ui
├── packages/
│   └── widget/
│       ├── src/index.ts
│       ├── package.json
│       └── tsconfig.json
├── docker-compose.yml                # web + api (Atlas for MongoDB)
├── Makefile
├── .env.example                      # Pointer to app-level env files
├── .gitignore
├── README.md
├── docs/
├── CLAUDE.md
└── LICENSE
```

## FastAPI App Details

### main.py

- FastAPI app with CORS middleware (origins from settings)
- Lifespan handler: initialize MongoDB + OpenAI on startup, cleanup on shutdown
- Include `health` router
- Port 8100

### routers/health.py

- `GET /health` — pings MongoDB, returns `{"status": "ok", "mongodb": "connected"}`
- Returns 503 if MongoDB unreachable

### Code migration from reference app

| Reference file | New location | Changes |
|---------------|-------------|---------|
| `src/settings.py` | `src/core/settings.py` | None |
| `src/dependencies.py` | `src/core/dependencies.py` | Update imports |
| `src/providers.py` | `src/core/providers.py` | Update imports |
| `src/prompts.py` | `src/core/prompts.py` | None |
| `src/tools.py` (SearchResult) | `src/models/search.py` | Extract model |
| `src/tools.py` (functions) | `src/services/search.py` | Update imports |
| `src/agent.py` | `src/services/agent.py` | Update imports |
| `src/ingestion/*.py` | `src/services/ingestion/*.py` | Update imports |
| `src/cli.py` | `src/cli.py` | Update imports |

### pyproject.toml

Based on reference app's, adding: `fastapi`, `uvicorn[standard]`. Dev deps add `httpx`.

## Next.js App Details

- `create-next-app` with App Router, TypeScript strict, Tailwind, ESLint
- shadcn/ui initialized (new-york style)
- Port 3100
- Default landing page only — dashboard pages in Phase 5

## Widget Package

- `package.json` with esbuild
- `src/index.ts` placeholder
- Build: `esbuild src/index.ts --bundle --minify --outfile=dist/widget.js`

## Docker Compose

Two services (`api`, `web`), no MongoDB container. Both apps connect to Atlas.

## Makefile Targets

| Target | Command |
|--------|---------|
| `dev` | Run api + web concurrently |
| `api` | `cd apps/api && uv run uvicorn src.main:app --reload --port 8100` |
| `web` | `cd apps/web && pnpm dev` |
| `install` | Install deps for both apps |
| `lint` | Run linters for both apps |
| `test` | Run test suites for both apps |
| `widget-build` | Build the widget bundle |

## Root Files

- **`.env.example`** — Pointer explaining env vars live in app-level files
- **`.gitignore`** — Extended for Python, Node, IDE artifacts
- **`README.md`** — Prerequisites, install, env config, running locally, Docker
