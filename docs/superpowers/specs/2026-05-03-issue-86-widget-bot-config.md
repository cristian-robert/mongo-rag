# Spec — Issue #86: Widget bot_id + public bot config + SSE restore

Date: 2026-05-03
Issue: https://github.com/cristian-robert/mongo-rag/issues/86
Branch: `feat/86-widget-bot-id-and-public-config`
Worktree: `.worktrees/86-widget-bot-config`

## Goal

Make the embeddable widget cosmetic config a function of the dashboard, not the embed snippet — while preserving explicit `data-*` overrides as the higher-priority source. Concurrently, restore SSE now that #84 has merged, and start sending `bot_id` so #85's backend bot resolution can wire up end-to-end.

## Three independent changes in one PR

| # | Change | Files |
|---|--------|-------|
| 1 | Restore SSE (`Accept: text/event-stream`, `parseSSE(response.body)`, `!response.body` guard) — revert the JSON adapter introduced in `0989dc3` | `packages/widget/src/api.ts` |
| 2 | Send `bot_id` in chat body when `config.botId` is set | `packages/widget/src/api.ts`, `packages/widget/src/widget.ts` |
| 3 | Fetch `GET ${apiUrl}/api/v1/bots/public/${botId}` at boot, merge into config with `data-*` precedence, re-render | new `packages/widget/src/publicBot.ts`, wire from `widget.ts` |

These are independent — none of them depends on the others to compile or test.

## Open questions resolved during brainstorm

### Q1 — Where does the public-fetch fire?

**A:** Inside `mountWidget` in `widget.ts`, after the launcher/panel are mounted with `data-*` defaults. The fetch is fire-and-forget. On success we mutate the live config snapshot, recreate the launcher/panel labels, restyle the shadow root, and re-run any first-message seeding that depended on `welcomeMessage`.

Reason: `index.ts` is a tiny boot trampoline; widget rendering and lifecycle live in `widget.ts`. The bootstrap path (`init()` → `buildConfig()` → `mountWidget()`) stays synchronous; the fetch is kicked off from inside `mountWidget` so it can also access the panel/launcher refs.

### Q2 — How does merge precedence get implemented without becoming a footgun?

**A:** We track which fields the embed script EXPLICITLY set (`dataAttributesConfig`-equivalent) by checking the `RawConfigInput` BEFORE defaults are filled in. Concretely: `parseScriptDataset` already returns `undefined` for fields the embed didn't set. So we keep a `RawConfigInput` snapshot of the embed (script + window) values, and after the public fetch we only adopt server values for fields where the snapshot was `undefined`.

Public-server values cover: `name` → `botName`, `welcome_message` → `welcomeMessage`, `widget_config.primary_color` → `primaryColor`, `widget_config.position` → `position`.

Anything else on the public payload (e.g. `slug`, `id`) is informational only and never touches widget rendering.

### Q3 — Re-render strategy

The launcher's `aria-label` and the panel's `<h2>` title and `aria-label` reference `config.botName`. The first assistant message uses `config.welcomeMessage`. Primary color is injected via `<style>` from `buildStyles({ primaryColor })`. Position is encoded into class names on launcher/panel.

Rather than rewrite the widget to a fully reactive model (overkill), expose `applyConfigUpdate(newConfig)` from `mountWidget` that:

1. Re-applies `aria-label` on launcher.
2. Re-applies `<h2>` `textContent` on the panel.
3. Re-applies `<dialog>` `aria-label` on the panel.
4. Replaces the `<style>` element's `textContent` with a fresh `buildStyles({ primaryColor })`.
5. Toggles position classes (`mrag-pos-right` ↔ `mrag-pos-left`) on launcher + panel.
6. If the launcher hasn't been opened yet (so the welcome message hasn't been seeded), nothing else needs touching. If it HAS been opened and the only message is the seeded welcome message, replace it. If the user has already typed and there are real messages, leave history alone — the cosmetic re-skin still applies.

### Q4 — Public payload safety test

Existing tests already lock this in:

- `apps/api/tests/test_bot_service.py::test_get_public_omits_secret_fields` — service-level
- `apps/api/tests/test_bot_router.py::test_public_bot_endpoint_unauthenticated` — router-level (asserts response JSON does not include `system_prompt`, `tenant_id`, `document_filter`)

We will ADD one strict allowlist test at the router layer that asserts the full set of response keys equals `{id, slug, name, welcome_message, widget_config}` — so any future field accidentally added to the response surfaces immediately as a test failure (including `tone`, `model_config`, `is_public`, etc.). This is the only backend file touched by this PR.

### Q5 — SSE restore exact diff

`git show 0989dc3 -- packages/widget/src/api.ts` shows:

- `Accept` header: `application/json` → restore to `text/event-stream`
- `if (!response.ok)` → restore to `if (!response.ok || !response.body)`
- `events: jsonResponseToEvents(response)` → restore to `events: parseSSE(response.body)`
- Drop the `ChatJsonResponse` interface and `jsonResponseToEvents` generator (no longer needed).
- Drop unused `ChatSource` import.
- Update the file header note: replace the "issue #84, temporary" paragraph with a one-line note that SSE is back now that #84 merged.

The existing api.test.ts already asserts `headers.Accept === "text/event-stream"` (the canary baseline failure that confirmed the workaround needed reverting).

## Test plan

### Widget (Vitest)

| Test | Purpose |
|------|---------|
| (existing) `buildAuthHeaders sets text/event-stream` | Restored — already failing, will pass once SSE restored |
| `ChatRequestBody includes bot_id when config.botId set` | New — type-only test won't catch this; we need a runtime test that exercises a fake `fetch` and inspects the request body |
| `widget passes bot_id from config to api body` | Equivalent — exercise widget send via mocked api |
| `fetchPublicBotConfig returns parsed config on 200` | New |
| `fetchPublicBotConfig returns null on non-200` | New |
| `fetchPublicBotConfig returns null on network error` | New |
| `mergePublicConfig prefers data-* over server values` | New |
| `mergePublicConfig uses server values when data-* is absent` | New |

### Backend (pytest)

| Test | Purpose |
|------|---------|
| `test_public_bot_response_has_strict_allowlist` | New — strict key set assertion |

### Manual (post-merge)

1. Start API on 8100, testWebApp on 3101.
2. Create a public bot with name `Acme Bot 1`, primary color `#3366ff`.
3. Set `data-bot-id="<bot_id>"` on the testWebApp embed (no other `data-*` overrides).
4. Open testWebApp → bubble shows `Acme Bot 1`, blue color.
5. Edit bot to name `Acme Bot 2`, color `#cc0066`. Reload testWebApp → bubble updates.
6. Add `data-bot-name="Override"` → bubble shows `Override`, color still `#cc0066` (data-* wins for name only).

## Acceptance criteria mapping

| AC | Implementation |
|----|----------------|
| `bot_id` in every chat body when `data-bot-id` set | Change 2 |
| `GET /api/v1/bots/public/{bot_id}` fires on boot | Change 3 |
| Dashboard edits → reload → new look | Change 3 |
| `data-*` overrides win | `mergePublicConfig` precedence rules |
| Network failure silent + non-blocking | `fetchPublicBotConfig` returns null on any throw |
| Public payload never leaks secrets | Backend strict-allowlist test |
| Vitest coverage of body, fetch+merge, failure, precedence | Listed in test plan |
| Manual against testWebApp | Listed in test plan |

## Out of scope (per issue)

- Live updates without reload
- Multi-bot per page
- Authenticated public-config endpoint
- Bot system prompt / tone / document_filter (#85's domain)
