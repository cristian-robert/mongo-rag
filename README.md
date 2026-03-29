# MongoRAG

Multi-tenant AI chatbot SaaS powered by RAG. Upload documents, get an embeddable chatbot that answers questions grounded in your own data.

## Architecture

- **apps/api** — FastAPI backend (Python, Pydantic AI, MongoDB Atlas Vector Search)
- **apps/web** — Next.js frontend (TypeScript, Tailwind CSS, shadcn/ui)
- **packages/widget** — Embeddable JS chat widget

## Prerequisites

- [Python 3.10+](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/) — Python package manager
- [Node.js 22+](https://nodejs.org/)
- [pnpm](https://pnpm.io/) — Node package manager
- [MongoDB Atlas](https://www.mongodb.com/atlas) account (free M0 tier works)

## Quick Start

### 1. Install dependencies

```bash
make install
```

### 2. Configure environment

```bash
# Backend
cp apps/api/.env.example apps/api/.env
# Edit apps/api/.env with your MongoDB URI and API keys

# Frontend
cp apps/web/.env.example apps/web/.env.local
# Edit apps/web/.env.local with your API URL
```

### 3. Run dev servers

```bash
make dev
```

This starts:
- API at http://localhost:8100
- Web at http://localhost:3100

### Individual services

```bash
make api    # FastAPI only
make web    # Next.js only
```

## Other Commands

```bash
make lint          # Run linters (ruff + eslint)
make test          # Run test suites
make widget-build  # Build the embeddable widget
make clean         # Remove build artifacts
```

## Docker

```bash
# Copy env files first (see step 2 above)
docker compose up --build
```

## Project Structure

```
mongo-rag/
├── apps/
│   ├── api/          # FastAPI backend
│   │   ├── src/
│   │   │   ├── core/       # Settings, dependencies, providers
│   │   │   ├── models/     # Pydantic models
│   │   │   ├── routers/    # API endpoints
│   │   │   ├── services/   # Business logic (agent, search, ingestion)
│   │   │   └── main.py     # App factory
│   │   └── tests/
│   └── web/          # Next.js frontend
├── packages/
│   └── widget/       # Embeddable chat widget
├── docs/             # Architecture, roadmap, plans
├── Makefile          # Dev scripts
└── docker-compose.yml
```

## Documentation

- [Architecture](docs/architecture.md)
- [Roadmap](docs/ROADMAP.md)
