---
description: Backend development rules — Python / FastAPI / MongoDB / Pydantic AI
globs: ["apps/api/**", "**/*.py"]
paths:
  - "apps/api/**"
---

# Backend Rules (Python / FastAPI)

## Skill Chain

1. **KB search** — `KB_PATH=.obsidian node cli/kb-search.js search "<keywords>"`
2. **architect-agent RETRIEVE** — understand current module structure before changes
3. **context7 MCP** — verify FastAPI / Pydantic / Motor / Pydantic AI / Stripe APIs (`resolve-library-id` → `query-docs`)
4. **MongoDB MCP** (if available) or direct queries — for schema/index changes
5. **Implement** — follow patterns from `.claude/references/code-patterns.md`
6. **architect-agent RECORD** — update knowledge base after structural changes
7. **KB update** — update wiki articles for new/changed modules, endpoints, patterns

## Backend Skill Recipe

- Call `architect-agent` RETRIEVE/IMPACT before structural changes
- Load `/fastapi-python` for endpoint patterns, dependency injection, async
- Load `/mongodb` or `/mongodb-development` for queries, aggregation, indexes
- Load `/pydantic-ai-agent-creation` when working on the RAG agent
- Load `/pydantic-ai-tool-system` when defining agent tools
- Load `/stripe-best-practices` when working on billing/subscriptions
- Use `context7` MCP to verify FastAPI / Pydantic / Motor APIs before writing code
- **Superpowers Mode adds:** `/superpowers:writing-plans`, `/superpowers:test-driven-development`, `/superpowers:verification-before-completion`

## Skill Trigger Map (Backend)

| Task | Skill |
|------|-------|
| FastAPI endpoints, middleware, deps | `/fastapi-python` |
| MongoDB queries, aggregation, indexes | `/mongodb` |
| MongoDB schema, collections, migrations | `/mongodb-development` |
| Pydantic AI agent logic | `/pydantic-ai-agent-creation` |
| Pydantic AI tool definitions | `/pydantic-ai-tool-system` |
| Stripe billing, subscriptions, webhooks | `/stripe-best-practices` |
| Library API verification | `context7` MCP |

## Conventions

- Async everywhere: `async def` for all handlers, `motor` (not `pymongo`) for MongoDB
- Pydantic models for request/response, not raw dicts
- Pydantic Settings for configuration (`src/settings.py`) — never raw `os.getenv`
- Type annotations on all function signatures and return types
- Tests with `pytest` + `pytest-asyncio`
- Structured logging with context (no print statements)
- Business logic in services, not routes
- **TENANT ISOLATION** — every MongoDB query includes `tenant_id` (most critical security boundary)

## Security (full list in `.claude/references/security-checklist.md`)

The five most-frequently-missed defaults — always check on auth/API/public-endpoint work:

- Passwords hashed with bcrypt/argon2 (≥12 rounds) — never plaintext
- Tokens in httpOnly cookies — never localStorage
- Input validation on every endpoint (Pydantic schemas)
- CORS restricted to allowlisted domains — never `*`
- No hardcoded secrets — env vars only

## Checklist

- [ ] All endpoints authenticated + authorized; tenant_id derived from auth, never trusted from client
- [ ] All inputs validated via Pydantic models
- [ ] No sensitive fields (hashes, tokens, PII) in API responses
- [ ] `uv run pytest` passes (unit + integration)
- [ ] `uv run ruff check . && uv run ruff format --check .` clean
- [ ] Wiki articles updated for structural changes
- [ ] architect-agent RECORD called for new modules/routes/collections

## References

Load only when the rule triggers:

- `.claude/references/code-patterns.md` — FastAPI / Pydantic / Hybrid RRF / MongoDB code patterns
- `.claude/references/backend-detail.md` — error formats, DI/layering, logging, testing-by-layer
- `.claude/references/security-checklist.md` — load for any auth, API, or infra change
- `.obsidian/wiki/_index.md` — search for feature articles when touching endpoints
