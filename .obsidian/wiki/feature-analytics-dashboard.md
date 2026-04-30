---
title: "Feature: Conversation analytics dashboard"
type: feature
tags: [feature, analytics, dashboard, observability]
sources:
  - "apps/api/src/services/analytics.py"
  - "apps/api/src/routers/analytics.py"
  - "apps/web/app/(dashboard)/dashboard/analytics/page.tsx"
  - "PR #62"
related:
  - "[[feature-rag-agent]]"
created: 2026-04-30
updated: 2026-04-30
status: compiled
---

## Overview

Per-tenant dashboard surfacing chat metrics: conversations, user queries, no-answer rate, top queries, daily timeseries, and a paginated query log with conversation-detail drill-down. Backed by MongoDB `$facet` aggregations over the `conversations` collection.

## GitHub Issues

| Issue | Title | Status |
|-------|-------|--------|
| (PR #62) | feat(analytics): conversation analytics dashboard | merged |

## Content

### API endpoints (`routers/analytics.py`, JWT-only)

- `GET /api/v1/analytics/overview?days=N` — totals + rates
- `GET /api/v1/analytics/timeseries?days=N` — daily counts
- `GET /api/v1/analytics/queries?days=N&page=&page_size=&no_answer=` — paginated query log
- `GET /api/v1/analytics/conversations/{id}` — full transcript

Window param: `days ∈ [1, 365]`, default 30. Pagination: `page_size ∈ [1, 100]`, default 25.

### Metrics computed (`services/analytics.py`)

**Overview ($facet):** total conversations, total messages, user queries, assistant responses, unique sessions, average response length, no-answer rate, top-10 queries.

**Timeseries:** daily counts of user queries + assistant responses over the window. Group key is the UTC date.

**Queries:** paginated user-query rows with answer preview (200 chars), sources count, optional no-answer filter.

**Conversation detail:** message-by-message with role, content, sources, timestamp.

All aggregations include `tenant_id` as the first match stage (compound index on `conversations.tenant_id + updated_at`).

### Frontend (`apps/web/app/(dashboard)/dashboard/analytics/page.tsx`)

- Server component; fetches overview + timeseries + queries in parallel
- URL-synced filters: `?days=`, `?page=`, `?no_answer=1`, `?conversation=<id>` (modal)
- Stat cards (conversations, questions, avg reply length, unanswered rate)
- Volume chart (`_components/volume-chart.tsx`) — queries vs answers per day
- Top queries list, queries table (paginated), conversation modal

### No-answer detection

A reply is "no-answer" when the assistant returns the configured fallback string (e.g. "I don't know based on the provided documents"). The flag is set at chat-completion time on the message record, not derived at query time, so the no-answer filter is index-friendly.

## Key Takeaways

- Single-collection (`conversations`) `$facet` aggregations — no separate analytics warehouse.
- Window clamped server-side to 1–365 days; pagination clamped to 1–100.
- Top queries aggregate the full window; cardinality kept low by deduplicating queries before tallying.
- Frontend is a server component with URL-synced filters; conversation drill-down is a modal driven by a query param.
- `no_answer` is computed at write time, not at analytics query time.

## See Also

- [[feature-rag-agent]] — produces the conversation records this dashboard reads
