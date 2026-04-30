---
title: "Feature: RAG pipeline enhancements (rerank, query rewrite, citations)"
type: feature
tags: [feature, rag, rerank, query-rewriting, citations]
sources:
  - "apps/api/src/services/rerank.py"
  - "apps/api/src/services/query_rewrite.py"
  - "apps/api/src/services/citations.py"
  - "apps/api/src/services/chat.py"
  - "PR #63"
related:
  - "[[feature-rag-agent]]"
  - "[[hybrid-rrf-search]]"
  - "[[feature-rag-eval-harness]]"
created: 2026-04-30
updated: 2026-04-30
status: compiled
---

## Overview

Three retrieval-quality features were added on top of hybrid RRF search: a pluggable reranker, optional query rewriting, and inline `[n]`-style citations resolved to a structured Pydantic model. They compose into the chat pipeline and are individually toggleable via settings.

## GitHub Issues

| Issue | Title | Status |
|-------|-------|--------|
| (PR #63) | feat(rag): pluggable reranker, query rewriting, inline citations | merged |

## Content

### Reranker — `services/rerank.py`

**Interface** — `Reranker` Protocol with single async method:

```python
async def rerank(query: str, results: list[SearchResult], top_n: int | None = None) -> list[SearchResult]: ...
```

**Implementations:**

- **`CohereReranker`** — calls Cohere `rerank-3.5` over HTTPS. Truncates input to 4000 chars/chunk and 2000 chars/query before sending.
- **`LocalCrossEncoderReranker`** — lazy-loads `sentence-transformers` `cross-encoder/ms-marco-MiniLM-L-6-v2`. Runs in a thread pool to avoid blocking the event loop.

**Factory** — `build_reranker(provider, api_key, model, timeout_s)` returns `None` when `provider` is `"off"` or unset; the retrieval orchestrator skips the rerank stage when None.

**Timeouts:** per-call default 1.5s, outer hard timeout 3× that in the orchestrator.

### Query rewriting — `services/query_rewrite.py`

**Entry point:**

```python
async def expand_query(query, enabled, deps, use_llm, max_expansions) -> list[str]
```

Returns 0–3 *additional* queries (the original is never substituted; expansions are merged via RRF alongside the original).

**Vague-query detection:** length ≤ 25 chars OR contains markers like `"how do i"`, `"what is"`, `"set this up"`. Non-vague queries skip rewriting entirely.

**Two modes:**

1. **Heuristic** (deterministic): strips vague markers, appends `"guide tutorial steps"` suffix.
2. **LLM-backed**: a Pydantic AI agent with a custom rewriting prompt parses one query per output line. Falls back to heuristic on parse error.

### Citations — `services/citations.py`

**`Citation` Pydantic model:**

| Field | Type |
|---|---|
| `marker` | int (1-based, the `[n]` index) |
| `chunk_id` | str |
| `document_id` | str |
| `document_title` | str |
| `document_source` | str |
| `snippet` | str (first 200 chars of chunk content) |
| `relevance_score` | float |
| `heading_path` | list[str] |
| `page_number` | int \| None |

**Pipeline:**

1. `build_citation_context(results)` — formats results as `"[n] title — heading\ncontent"` plain-text blocks (no XML/JSON, kept token-light)
2. The LLM emits `[n]` markers inline in its answer
3. `extract_citation_indices(text)` — regex `\[(\d{1,2})\]` over the answer, ordered, deduped
4. `resolve_citations(answer, results)` — maps indices to `Citation` objects, validates against the result count

The `ChatResponse` API surface returns the `citations` list alongside the answer text.

### Composition in the chat pipeline

`services/chat.py` orchestrates per-message:

1. `expand_query` (optional) → list of [original + 0..3 rewrites]
2. For each: hybrid RRF search → results
3. Merge results by RRF a second time across queries
4. `Reranker.rerank` (optional) → trim to `top_n`
5. `build_citation_context` → prompt assembly
6. LLM streams answer (SSE) or returns sync answer (REST/JSON)
7. `resolve_citations(answer, results)` → final response

Toggles live in `settings`: `rerank_provider`, `query_rewrite_enabled`, `citation_*`. All default to safe-off-or-heuristic in tests.

## Key Takeaways

- Reranker is opt-in via `rerank_provider="off|cohere|local"`; default `"off"` returns `None` factory and the stage is skipped.
- Query rewriting only fires for vague queries; the original is always preserved (RRF-merged).
- Citations are typed (`Citation` Pydantic model) — the API contract is a list of these, not a stringly-typed list of marker numbers.
- All three features live in `services/`, are unit-testable in isolation, and are composed in `services/chat.py`.

## See Also

- [[feature-rag-agent]] — broader RAG agent composition
- [[hybrid-rrf-search]] — the retrieval base layer all three sit on top of
- [[feature-rag-eval-harness]] — how regression-test these enhancements
