---
title: "Feature: RAG Agent"
type: feature
tags: [feature, rag, search, pydantic-ai]
sources: []
related:
  - "[[hybrid-rrf-search]]"
  - "[[feature-document-ingestion]]"
  - "[[decision-pydantic-ai-over-langchain]]"
created: 2026-04-29
updated: 2026-04-29
status: active
---

## Summary

The customer-facing chatbot. A Pydantic AI agent with hybrid-search tools that answers questions grounded in tenant documents. Exposed via `/api/v1/chat` with both streaming SSE and synchronous responses.

## GitHub Issues

| Issue | Title | Status |
|-------|-------|--------|
| — | (link issues here as they are created) | — |

## Key Decisions

- **Pydantic AI over LangChain** — see [[decision-pydantic-ai-over-langchain]]
- **Pluggable LLM/embedding providers** — `apps/api/src/providers.py` abstracts OpenAI / OpenRouter / Ollama / Gemini behind a single interface
- **Streaming via SSE** — Server-Sent Events, not WebSockets, for simpler infra and reverse-proxy compatibility

## Implementation Notes

- Entry point: `apps/api/src/agent.py`
- Tools: `apps/api/src/tools.py` (hybrid_search is the primary tool)
- Prompts: `apps/api/src/prompts.py` (versioned system prompt templates)
- Conversation history persisted in `conversations` collection, scoped by `tenant_id`
- The agent always passes `tenant_id` into search tools via PydanticAI dependencies, never via prompt
- Token-count limits enforced before each LLM call to avoid runaway costs

## Key Takeaways

- The agent never reads MongoDB directly — it goes through the search tool, which enforces tenant isolation
- LLM provider is configurable per-deployment via env vars (`LLM_MODEL`); the agent code stays provider-agnostic
- System prompts live in `prompts.py` and are versioned — old conversations replay against the prompt that produced them

## See Also

- [[hybrid-rrf-search]] — the retrieval tool the agent calls
- [[feature-document-ingestion]] — produces the chunks the agent searches
- [[decision-pydantic-ai-over-langchain]] — why we chose this framework
