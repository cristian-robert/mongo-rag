# Spec: #85 — wire bot config into ChatService

## Problem

Editing a bot in the dashboard ("Bot settings" — system prompt, tone, product name, document_filter) saves to the `bots` Mongo collection, but the chat path ignores those fields. Three independent gaps:

1. `ChatRequest` has no `bot_id` field (`apps/api/src/models/api.py:168-180`).
2. `ChatService` calls `create_rag_agent()` with no args (`apps/api/src/services/chat.py:150,190`) → defaults to `"this product"` and the static template.
3. No tenant-isolated bot lookup on the chat path.

## Story

When a tenant edits a bot's `system_prompt`, the very next chat for that bot honors the new prompt. When `document_filter.mode == "ids"` is set, retrieval is restricted to those document_ids.

## Design decisions

### Bot resolution path

- Single resolution point at top of `ChatService._prepare_chat`. Both `handle_message` and `handle_message_stream` go through `_prepare_chat`, so one call site covers both transports.
- `_resolve_bot(bot_id, tenant_id) -> dict | None`. Tenant-scoped via `BotService.get(bot_id, tenant_id)` (which already enforces tenant isolation by Mongo filter).
- `bot_id` shape: 24-hex ObjectId string. `BotService.get` already returns `None` for invalid OIDs and for cross-tenant lookups.
- 404 (`BotNotFoundError`) when `bot_id` was supplied but `_resolve_bot` returns `None`. This applies to both wrong-tenant and unknown-id, mirroring `BotService.get`. We mirror the existing `ConversationNotFoundError` pattern.

### Prompt composition

Per the issue: "bot.system_prompt overrides the static template if present, otherwise apply tone suffix on top of build_system_prompt(product_name)".

Since `BotBase.system_prompt` is required (`min_length=10`), the tone-suffix path is effectively reserved for forward-compat. Codify both branches anyway:

```python
def _compose_system_prompt(bot: dict) -> str:
    sp = (bot.get("system_prompt") or "").strip()
    product = bot.get("name") or "this product"
    base = sp if sp else build_system_prompt(product)
    if not sp:
        suffix = TONE_SUFFIXES.get(bot.get("tone", "professional"), "")
        if suffix:
            return f"{base}\n\n{suffix}"
    return base
```

`product_name` source: bot doc has `name`, not `product_name` — `BotBase` exposes only `name`. The issue text says `bot["product_name"]` — that field doesn't exist in the model. Use `bot["name"]`. (Defensible: the `name` IS what the customer calls their product in their bot config.)

### Default fallback (no bot_id)

- `bot_id` omitted → resolved bot is `None` → legacy default prompt path: `create_rag_agent()` with no args (= `build_system_prompt("this product")`). Preserves backwards compat for CLI / eval flows.
- We do NOT auto-pick a tenant's "first" bot — too risky. Caller passes bot_id explicitly or gets the default.
- Per the issue: "require it for widget API keys (decide based on Principal.kind == 'widget' if that distinction exists; otherwise validate at the handler)." The current `Principal` model has `auth_method: "jwt" | "api_key"` — no widget kind. We do NOT enforce bot_id at handler level. Documented as a follow-up.

### document_filter wiring

`bot["document_filter"]` shape: `{"mode": "all"|"ids", "document_ids": [str, ...]}`.
- `mode == "all"` → no filter.
- `mode == "ids"` and `document_ids` non-empty → retrieval restricted to those ObjectIds.

Plumbing:
- Add `document_ids: Optional[list[str]] = None` to `RetrievalOptions`.
- `retrieve()` passes through to `semantic_search` and `text_search` via new optional `document_ids` parameter.
- In `semantic_search` ($vectorSearch filter): `filter` becomes `{"tenant_id": ..., "document_id": {"$in": [ObjectId(d) for d in document_ids]}}`.
- In `text_search` ($search compound filter[]): add `{"in": {"path": "document_id", "value": [ObjectId(d) for d in document_ids]}}`.
- Cast strings to ObjectId; skip invalid ones with a warning.
- Empty document_ids list when `mode == "ids"` → return zero results (deliberate: filter says "only these ids", and there are none).

### Logging

When a bot loads:
```python
logger.info("chat_bot_resolved", extra={"bot_id": bot_id, "tenant_id": tenant_id, "doc_filter_mode": bot["document_filter"]["mode"]})
```
Never log `system_prompt`.

## Test plan (per acceptance criterion)

| AC | Test |
|---|---|
| `ChatRequest.bot_id` accepted/validated | `test_models_api.py` — pydantic round-trip, length cap |
| `_resolve_bot` filters by tenant + 404s on miss | `test_chat_service.py::test_resolve_bot_*` |
| Custom system_prompt is the agent's system_prompt | `test_chat_service.py::test_custom_system_prompt_used` |
| `document_filter` applied to retrieval | `test_chat_service.py::test_document_filter_passed`, `test_search_tenant.py::test_document_filter_*` |
| Default-bot fallback w/o bot_id | `test_chat_service.py::test_no_bot_id_uses_default_prompt` |
| Cross-tenant bot_id rejected | `test_chat_service.py::test_cross_tenant_bot_id_rejected` |
| Updating system_prompt reflects in next chat | covered by no-cache resolution (always re-fetches) — assert via the custom-prompt test |
| `create_rag_agent` accepts system_prompt | `test_agent.py::test_create_rag_agent_with_system_prompt` |
| Tone suffix applied when system_prompt absent | `test_chat_service.py::test_tone_suffix_applied_when_no_system_prompt` |
| Integration: end-to-end | `test_chat_router.py::test_chat_with_custom_bot` (mocked agent) |
