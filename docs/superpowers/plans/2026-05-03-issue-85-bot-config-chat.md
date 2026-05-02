# Plan: #85 — wire bot config into ChatService

## Mandatory reading (no prior knowledge test)

- `apps/api/src/services/chat.py` — `_prepare_chat`, `handle_message`, `handle_message_stream`
- `apps/api/src/services/bot.py` — `BotService.get` (tenant filter)
- `apps/api/src/services/agent.py` — `create_rag_agent` signature
- `apps/api/src/services/retrieval.py` — `RetrievalOptions`, `retrieve`
- `apps/api/src/services/search.py` — `semantic_search`, `text_search`
- `apps/api/src/models/api.py` — `ChatRequest`
- `apps/api/src/models/bot.py` — `BotBase`, `DocumentFilter`, `BotTone`
- `apps/api/src/core/principal.py` — `Principal`, `tenant_filter`, `tenant_doc`
- `apps/api/src/core/prompts.py` — `build_system_prompt`
- `apps/api/src/routers/chat.py` — chat endpoint, both paths
- Tests: `tests/test_bot_service.py`, `tests/test_chat_router.py`, `tests/test_search_tenant.py`, `tests/test_retrieval_pipeline.py`, `tests/test_tenant_filter_audit.py`

## Tasks (ordered, TDD: red → green → refactor → commit)

### Task 1 — `ChatRequest.bot_id` field
- **Red**: add `tests/test_chat_request_bot_id.py` (or extend `test_chat_router.py`) — invalid charset is rejected; valid 24-hex accepted; len cap enforced.
- **Impl**: `apps/api/src/models/api.py` — add `bot_id: Optional[str] = Field(default=None, max_length=64, ...)`.
- **Commit**: `feat(api): accept optional bot_id in ChatRequest (#85)`

### Task 2 — `create_rag_agent(system_prompt, product_name)` signature
- **Red**: extend `tests/test_agent.py` (create if missing) — passing `system_prompt="X"` makes the agent use that exact prompt; absent → falls back to `build_system_prompt(product_name)`.
- **Impl**: `apps/api/src/services/agent.py` — change signature to `(system_prompt: Optional[str] = None, product_name: str = "this product")`.
- **Commit**: `feat(api): create_rag_agent accepts custom system_prompt (#85)`

### Task 3 — `ChatService._resolve_bot` + tenant isolation
- **Red**: extend `tests/test_chat_service.py` — `_resolve_bot` returns the bot dict; returns `None` for `None` id; raises on cross-tenant.
- **Impl**: add `_resolve_bot(bot_id, tenant_id)` to `ChatService` that delegates to `BotService.get`.
- **Commit**: `feat(api): ChatService._resolve_bot via BotService.get (#85)`

### Task 4 — Prompt composition helper
- **Red**: tests for `_compose_system_prompt` — bot.system_prompt overrides; product_name pulled from bot.name; tone suffix applied when system_prompt absent.
- **Impl**: add `_compose_system_prompt(bot)` and `TONE_SUFFIXES` table to `chat.py` (or a tiny new module if it grows).
- **Commit**: `feat(api): compose bot-aware system prompt (#85)`

### Task 5 — `document_filter` wiring through retrieval
- **Red**: extend `tests/test_search_tenant.py` — semantic_search/text_search with `document_ids=["..."]` build the right $vectorSearch filter / $search compound filter.
- **Impl**: add `document_ids: Optional[list[str]] = None` to `RetrievalOptions`; thread through `retrieve` → `_run_base_search` → `semantic_search` / `text_search` / `hybrid_search`.
- **Commit**: `feat(api): document_filter wiring through retrieval pipeline (#85)`

### Task 6 — Wire bot resolution into `_prepare_chat` and both handlers
- **Red**: extend `tests/test_chat_service.py` — `handle_message` with `bot_id` calls `create_rag_agent(system_prompt=..., product_name=...)`; `handle_message_stream` likewise.
- **Impl**: thread `bot_id` through `handle_message` / `handle_message_stream` / `_prepare_chat` → resolve bot → compose prompt → pass to `create_rag_agent` → also pass `document_ids` to `retrieve`.
- **Commit**: `feat(api): wire bot config into ChatService (#85)`

### Task 7 — Default fallback (no bot_id)
- **Red**: `test_chat_service.py::test_no_bot_id_uses_default_prompt` — agent built with no system_prompt arg.
- **Impl**: covered by Task 6 (no-op when `bot_id` is `None`); test only.
- **Commit**: covered by Task 6.

### Task 8 — Router thread-through
- **Red**: extend `tests/test_chat_router.py` — request body with `bot_id` flows to `ChatService.handle_message`; non-existent bot_id returns 404.
- **Impl**: `apps/api/src/routers/chat.py` — pass `body.bot_id` to both service calls; map `BotNotFoundError` → 404.
- **Commit**: `feat(api): thread bot_id through chat router and SSE path (#85)`

### Task 9 — Tenant isolation + audit
- Run `pytest tests/test_tenant_filter_audit.py` — must not surface new violations.
- **Commit**: rolled into Task 6/8 (no separate commit unless allowlist needs touching).

### Task 10 — Integration test (end-to-end with mocked agent)
- **Red**: `test_chat_router.py::test_chat_with_custom_bot` — full POST `/api/v1/chat` with `bot_id`; mock `create_rag_agent` to capture the system_prompt arg; assert it equals the bot's stored prompt.
- **Commit**: rolled into Task 8.

## Verification

```
cd apps/api
uv run ruff format --check .
uv run ruff check .
uv run pytest -m unit -q --deselect tests/test_tenant_filter_audit.py::test_every_mongo_call_in_apps_api_is_tenant_scoped
uv run pytest -m integration -q --deselect tests/test_tenant_filter_audit.py::test_every_mongo_call_in_apps_api_is_tenant_scoped
```

All four must be clean.

## Risks / Out of scope

- WebSocket chat: shares `ChatService.handle_message_stream` so the fix applies; `WSMessage` does NOT yet carry `bot_id`. Out of scope (separate field, separate transport-side test). Documented as follow-up.
- Widget-side `bot_id` send + public bot config fetch: companion #86 worktree.
- Per-bot rate limiting / quotas: out of scope.
- Tone behavior is a thin, optional layer (system_prompt is required on the model so tone is dead-weight today). Codified for forward compat.
