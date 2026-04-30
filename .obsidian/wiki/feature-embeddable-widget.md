---
title: "Feature: Embeddable chat widget"
type: feature
tags: [feature, widget, embed, sse, shadow-dom]
sources:
  - "packages/widget/src/index.ts"
  - "packages/widget/src/styles.ts"
  - "packages/widget/src/api.ts"
  - "packages/widget/Dockerfile"
  - "PR #51"
related:
  - "[[feature-rag-agent]]"
  - "[[feature-api-key-management]]"
  - "[[feature-bot-configuration]]"
created: 2026-04-30
updated: 2026-04-30
status: compiled
---

## Overview

A self-contained JavaScript chat widget that customers embed on their own site with a single `<script>` tag. The widget streams chat responses from the MongoRAG backend via SSE, isolates its CSS from the host page using closed Shadow DOM, and authenticates with an API key.

## GitHub Issues

| Issue | Title | Status |
|-------|-------|--------|
| (PR #51) | feat(widget): build embeddable chat widget with SSE streaming | merged |

## Content

### Embedding pattern

```html
<script src="https://cdn.mongorag.com/widget.js"
        data-api-key="mrag_..."
        data-bot-id="..."
        data-primary-color="#4f46e5"
        data-position="bottom-right"
        data-welcome-message="Hi! Ask me anything."
        data-show-branding="true"></script>
```

`packages/widget/src/index.ts` reads `document.currentScript`, parses the `data-*` attributes plus an optional `window.MongoRAG` object, validates, and mounts the widget into `document.body`.

**Programmatic mount:** `window.MongoRAG.mount(config)` for SPAs that need to remount on navigation.

### Bundle build

`esbuild` IIFE bundle:

```bash
esbuild src/index.ts --bundle --minify --outfile=dist/widget.js --format=iife --target=es2020
```

Output is a single self-executing file with no external dependencies.

### Shadow DOM isolation

`attachShadow({ mode: "closed" })` on the host element. The host gets:

- `data-mongorag-widget=""` attribute
- `style="all: initial;"` to neutralize cascading host CSS

A single `<style>` element is injected into the shadow root; all selectors are prefixed `.mrag-` for belt-and-braces protection. CSS variables expose `--mrag-primary` for runtime color customization. System font stack only — no external font loads. `prefers-reduced-motion` honored.

### Config validation

Strictly validated at mount:

- `api-key` must start with `mrag_` (otherwise the widget refuses to mount)
- `primary-color` matched against `/^(#[0-9a-fA-F]{3,8}|rgb\([\d,\s]+\)|rgba\([\d,.\s]+\))$/`
- `position` whitelisted to `"bottom-left" | "bottom-right"`
- `show-branding` parsed as boolean

### Transport (SSE)

`packages/widget/src/api.ts` uses `fetch` + `ReadableStream` over `POST /api/v1/chat`:

```http
Authorization: Bearer mrag_...
Accept: text/event-stream
```

Request body: `{ message, conversation_id?, search_type? }`.

Event stream (NDJSON-style `data: {...}\n\n`):

| Event | Shape |
|---|---|
| `token` | `{ type: "token", content: "<text chunk>" }` |
| `sources` | `{ type: "sources", sources: [{document_title, heading_path, snippet}] }` |
| `done` | `{ type: "done", conversation_id: "<id>" }` |
| `error` | `{ type: "error", message: "..." }` |

The widget uses the conversation_id from `done` for follow-up turns to maintain session context. (The full event set on the backend includes `citations` and `rewritten_queries` — the widget renders the subset above.)

### Bot-aware behavior

If `data-bot-id` is set, the API picks the bot's `system_prompt`, `welcome_message`, `tone`, and `widget_config` (primary color override, avatar, etc.) — see `[[feature-bot-configuration]]`. The widget can read public bot config without auth via `GET /api/v1/bots/{bot_id}/public` to render branding before the first message.

### Hosting

`packages/widget/Dockerfile` ships an nginx:1.27.3-alpine image (build stage uses node:22.12-alpine):

- Port **8080** (non-privileged), non-root user `widget:widget` (uid 1001)
- `/healthz` returns 200
- Cache headers: `Cache-Control: public, max-age=300`
- CORS: `*` (the script must load from any host)

GHCR image published as `ghcr.io/<owner>/mongo-rag/widget:<tag>`.

## Key Takeaways

- Single IIFE bundle; no external dependencies; no module loader required on the host page.
- Closed Shadow DOM + `style="all: initial"` + `.mrag-` prefix = three-layer CSS isolation.
- Auth is API-key Bearer (`mrag_*`) — the same key the customer creates in the dashboard.
- SSE over `POST /api/v1/chat`. The widget renders a subset of event types — `token`, `sources`, `done`, `error`.
- Bot id is optional but unlocks per-bot prompt + welcome + widget styling.

## See Also

- [[feature-api-key-management]] — where customers create the `mrag_*` key the widget uses
- [[feature-bot-configuration]] — where per-bot prompt and widget styling come from
- [[feature-rag-agent]] — the chat backend the widget streams from
