---
title: "Feature: Multi-tenant bot configuration"
type: feature
tags: [feature, bots, config, widget]
sources:
  - "apps/api/src/services/bot.py"
  - "apps/api/src/routers/bots.py"
  - "PR #53"
related:
  - "[[feature-embeddable-widget]]"
  - "[[feature-rag-agent]]"
created: 2026-04-30
updated: 2026-04-30
status: compiled
---

## Overview

Each tenant can define multiple chatbots, each with its own system prompt, model selection, document filter, and widget styling. The embeddable widget picks a bot via `data-bot-id`, and the API has a *public* read endpoint so the widget can render branding before any auth-gated message goes through.

## GitHub Issues

| Issue | Title | Status |
|-------|-------|--------|
| (PR #53) | feat(bots): multi-tenant bot configuration and management | merged |

## Content

### Storage — MongoDB `bots` collection

Per-document fields (tenant-scoped):

- `name`, `slug` (unique per tenant), `description`
- `system_prompt`, `welcome_message`, `tone`, `is_public`
- `model_config_` — `{ temperature, max_tokens }` (underscore-suffixed to avoid shadowing Pydantic's `model_config`)
- `widget_config` — `{ primary_color, position, avatar_url }`
- `document_filter` — `{ mode: "all" | "specific", document_ids: list[str] }`

**Cap:** 50 bots per tenant (hard limit at the service layer).

### Service interface — `services/bot.py`

| Method | Auth | Notes |
|---|---|---|
| `create(tenant_id, body)` | JWT | rejects on hitting the 50-bot cap |
| `list_for_tenant(tenant_id)` | JWT | full record |
| `get(bot_id, tenant_id)` | JWT | tenant-scoped, returns None on cross-tenant |
| `update(bot_id, tenant_id, body)` | JWT | partial update |
| `delete(bot_id, tenant_id)` | JWT | hard delete |
| `get_public(bot_id)` | unauthenticated | returns only widget-relevant non-secret fields |

### Public read for widgets

`get_public(bot_id)` returns a subset suitable for unauthenticated browser fetches:

- `name`, `welcome_message`, `tone`, `widget_config`
- NOT: `system_prompt`, `document_filter`, `model_config_`

This lets the widget render branding immediately on page load while keeping the system prompt and document scope private. The audit allow-list documents this as one of the few code paths that intentionally reads from `bots` without a tenant filter (`bot_id` is the lookup key; the public projection is what makes it safe).

### `document_filter` semantics

When a chat message hits a bot:

- `mode: "all"` — full tenant document set is searchable
- `mode: "specific"` — retrieval is restricted to `document_ids`. Combined with the tenant filter, this gives "this bot only answers from these documents" semantics.

### Endpoints (`routers/bots.py`)

- `GET /api/v1/bots` — list (JWT)
- `POST /api/v1/bots` — create (JWT, owner/admin)
- `GET /api/v1/bots/{id}` — get (JWT, tenant-scoped)
- `PATCH /api/v1/bots/{id}` — update (JWT)
- `DELETE /api/v1/bots/{id}` — delete (JWT)
- `GET /api/v1/bots/{id}/public` — anonymous; widget-safe subset

## Key Takeaways

- Per-bot system prompt + welcome + tone + widget styling + document filter.
- 50 bots/tenant hard cap.
- Public read endpoint is intentional and audited; widget renders branding pre-auth, but only sees a non-secret subset.
- `document_filter.mode="specific"` is how a bot is scoped to a subset of the tenant's documents.

## See Also

- [[feature-embeddable-widget]] — primary consumer of the public bot read
- [[feature-rag-agent]] — applies `system_prompt`, `model_config_`, and `document_filter` at chat time
