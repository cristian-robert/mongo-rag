---
title: "Decision: Pydantic AI over LangChain"
type: decision
tags: [decision, pydantic-ai]
sources:
  - "CLAUDE.md.backup architecture rationale"
related:
  - "[[feature-rag-agent]]"
created: 2026-04-29
updated: 2026-04-29
status: accepted
---

## Summary

We chose Pydantic AI for the RAG agent instead of LangChain because it fits FastAPI naturally, has a far smaller surface area, and treats type safety as a first-class concern.

## Context

The agent layer needed: tool calling, structured outputs, streaming, conversation memory, and pluggable LLM providers. Both LangChain and Pydantic AI cover this. The team's stack is already FastAPI + Pydantic + Motor, so adding LangChain meant introducing a parallel set of conventions, a heavier dependency tree, and an abstraction layer (Runnables / chains) that doesn't compose cleanly with FastAPI's dependency injection.

## Decision

Use [Pydantic AI](https://ai.pydantic.dev) as the agent framework.

- Tools are plain Python functions decorated with `@agent.tool`, signature-typed via Pydantic — same model layer used everywhere else in the API
- Dependencies (the `tenant_id`, the DB handle) flow through Pydantic AI's `RunContext`, which fits FastAPI's DI mental model
- Streaming uses `agent.run_stream()` and yields chunks compatible with FastAPI's `StreamingResponse` / SSE
- Provider switching is one env var (`LLM_MODEL`) — Pydantic AI supports OpenAI, Anthropic, OpenRouter, Ollama, Gemini natively

## Consequences

**Positive:**
- Smaller dependency footprint, faster cold starts
- Type safety end-to-end (request → tool → response)
- Less abstraction to debug — stack traces stay close to the actual call sites
- One mental model for the whole API (Pydantic models, FastAPI DI, async)

**Tradeoffs accepted:**
- Smaller ecosystem of pre-built integrations than LangChain
- Some advanced patterns (multi-agent orchestration, complex chains) require more manual code
- Newer library — fewer Stack Overflow answers, more reliance on official docs and source

**Mitigation:** Lock the version in `pyproject.toml` and bump deliberately; route real questions to the `/pydantic-ai-agent-creation` and `/pydantic-ai-tool-system` skills.

## Key Takeaways

- All agent code stays in `apps/api/src/agent.py` and `tools.py` — never a separate "chains" or "runnables" layer
- Tool functions take typed args and a `RunContext[Deps]` — never untyped `**kwargs`
- Use `/pydantic-ai-agent-creation` and `/pydantic-ai-tool-system` skills before touching this code

## See Also

- [[feature-rag-agent]] — the implementation that depends on this choice
