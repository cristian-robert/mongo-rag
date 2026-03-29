---
paths:
  - "apps/api/**"
---

# Backend Development Rules (Python / FastAPI)

## context7 MCP — Verify APIs Before Writing Code

Use `context7` MCP (`resolve-library-id` → `query-docs`) to verify APIs:

- FastAPI, Pydantic, Motor (async MongoDB driver), Stripe API patterns
- Don't rely on training data for these libraries

## Backend Skill Recipe

- Call `architect-agent` RETRIEVE/IMPACT before structural changes
- Load `/fastapi-python` for endpoint patterns, dependency injection, async patterns
- Load `/mongodb` or `/mongodb-development` for queries, aggregation pipelines, indexes
- Load `/pydantic-ai-agent-creation` when working on the RAG agent
- Load `/pydantic-ai-tool-system` when defining agent tools
- Load `/stripe-best-practices` when working on billing/subscriptions
- Use `context7` MCP to verify FastAPI/Pydantic/Motor APIs before writing code
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

## Python Code Standards

- Async everywhere: `async def` for all handlers, use `motor` for MongoDB
- Pydantic models for request/response, not raw dicts
- Pydantic Settings for configuration (`src/settings.py`)
- Structured logging with `structlog` or similar
- Type annotations on all functions
- Tests with `pytest` + `pytest-asyncio`
