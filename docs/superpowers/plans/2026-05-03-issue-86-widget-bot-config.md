# Implementation plan — Issue #86: Widget bot_id + public bot config + SSE restore

This plan is self-contained — passes the "no prior knowledge" test. Anyone reading just this file should be able to execute it.

## Required reading

1. Issue body — `gh issue view 86`
2. Spec — `docs/superpowers/specs/2026-05-03-issue-86-widget-bot-config.md`
3. Files (in order):
   - `packages/widget/src/api.ts`
   - `packages/widget/src/widget.ts`
   - `packages/widget/src/index.ts`
   - `packages/widget/src/config.ts`
   - `packages/widget/src/types.ts`
   - `packages/widget/tests/api.test.ts`, `widget.test.ts`, `config.test.ts`
   - `apps/api/src/routers/bots.py` (read-only, public route at line 109)
   - `apps/api/src/services/bot.py:172` (read-only, `get_public`)
   - `apps/api/src/models/bot.py:161` (read-only, `PublicBotResponse`)
   - `apps/api/tests/test_bot_router.py:243` (read-only, existing public tests)
4. Diff of the workaround commit being reverted: `git show 0989dc3 -- packages/widget/src/api.ts`

## Branch + worktree

- Worktree: `.worktrees/86-widget-bot-config`
- Branch: `feat/86-widget-bot-id-and-public-config` (already created off `origin/main` at `cfb1d79`)
- Always `cd` into the worktree before any shell command.

## Tasks (TDD — red → green → commit)

### Task 1 — Restore SSE in widget

State: red baseline already exists (`tests/api.test.ts:8` expects `text/event-stream`).

1. Edit `packages/widget/src/api.ts`:
   - Replace the file-header `NOTE (issue #84, temporary)` paragraph with a short note that SSE is back as of #86 (post-#84).
   - Drop unused `ChatSource` import (only `SSEEvent` needed).
   - `Accept: "application/json"` → `Accept: "text/event-stream"`.
   - `if (!response.ok)` → `if (!response.ok || !response.body)`.
   - `events: jsonResponseToEvents(response)` → `events: parseSSE(response.body)`.
   - Delete `ChatJsonResponse` interface and `jsonResponseToEvents` generator.
2. Run `pnpm -C packages/widget test` — all green.
3. Run `pnpm -C packages/widget build` — clean.
4. Commit: `revert(widget): restore SSE Accept header now that #84 has merged`.

### Task 2 — Send bot_id in chat body

1. RED: extend `tests/widget.test.ts` (or add new `tests/api.bot-id.test.ts`) — assert that when `widget.ts:send` runs with a config including `botId`, the body passed to `startChatStream` includes `bot_id`. Easiest path: write a small unit test against a thin helper. We will introduce `buildChatBody(config, message, conversationId)` in `widget.ts` and unit-test it directly so we don't have to mock fetch + DOM.
2. Add `bot_id?: string` to `ChatRequestBody` in `api.ts`.
3. Add `buildChatBody` helper (exported from `widget.ts`) that takes `(config, message, conversationId)` and returns `ChatRequestBody`. Replace the inline body-builder at `widget.ts:83`.
4. Add a `tests/widget.test.ts` block:
   - `buildChatBody includes bot_id when config.botId is set`
   - `buildChatBody omits bot_id when config.botId is undefined`
   - `buildChatBody includes conversation_id when provided`
5. Green. Commit: `feat(widget): send bot_id in chat request body`.

### Task 3 — Public bot config fetch + merge module

1. RED: create `tests/publicBot.test.ts` covering:
   - `fetchPublicBotConfig returns parsed shape on 200`
   - `fetchPublicBotConfig returns null on 404`
   - `fetchPublicBotConfig returns null on network throw`
   - `mergePublicConfig prefers explicit raw values over server values`
   - `mergePublicConfig uses server values when explicit raw value is undefined`
   - `mergePublicConfig validates server color/position via the same safeColor/safePosition path as buildConfig` (so server can't poison styles)
2. Create `packages/widget/src/publicBot.ts` exporting:
   - `interface PublicBotConfig { id, slug, name, welcome_message, widget_config: { primary_color, position, avatar_url? } }`
   - `async function fetchPublicBotConfig(apiUrl: string, botId: string, signal?: AbortSignal): Promise<PublicBotConfig | null>` — uses `fetch` with `cache: "force-cache"`, returns null on `!response.ok`, returns null on any throw, validates the JSON shape minimally.
   - `function mergePublicConfig(current: WidgetConfig, raw: RawConfigInput, server: PublicBotConfig): WidgetConfig` — for each of `botName`, `welcomeMessage`, `primaryColor`, `position`, only override when `raw.<field>` was undefined; pass server color/position through `safeColor`/`safePosition` (re-export those or move to a shared helper module).
3. Refactor `config.ts` so `safeColor`, `safePosition`, `safeText` are exported (they are currently file-private). Adjust their imports in `publicBot.ts`.
4. Green. Commit: `feat(widget): add public bot config fetch + merge helper`.

### Task 4 — Wire fetch into widget bootstrap with re-render

1. RED: extend `tests/widget.test.ts` (or new `tests/widget.public.test.ts`) — exercise `mountWidget` against happy-dom + a mocked `globalThis.fetch`:
   - `mountWidget kicks off public-config fetch when botId is set`
   - `mountWidget skips fetch when botId is unset`
   - `after fetch resolves, launcher aria-label reflects server botName`
   - `after fetch resolves, primary-color style is updated`
   - `data-* override on botName persists after fetch resolves`
   - `network failure does not throw and widget still mounts with data-* defaults`
   The cleanest implementation is to plumb the raw `RawConfigInput` snapshot AND a `fetchPublicBotConfig`-like fn through `mountWidget`'s options so the test can inject a stub. We'll widen `mountWidget(config, options?)` where `options` carries `{ rawInput?: RawConfigInput; fetchPublic?: typeof fetchPublicBotConfig }`. `index.ts` passes the real `parseScriptDataset/window-merged` raw input + the real fetcher. Tests pass stubs.
2. Implement `applyConfigUpdate(newConfig)` inside `mountWidget`. Call it from a single `then(...)` after the fetch promise resolves with a non-null result.
3. Update `index.ts` to compute the raw input (`mergeConfig(windowCfg, datasetCfg)`) and pass it to `mountWidget` along with the real fetcher.
4. Green. Commit: `feat(widget): fetch public bot config at boot and re-render with server values`.

### Task 5 — Backend strict-allowlist test

1. RED: add `apps/api/tests/test_bot_router.py::test_public_bot_response_has_strict_allowlist`:
   - Mock `BotService.get_public` to return a doc that ALSO contains forbidden keys (`system_prompt`, `tenant_id`, `document_filter`, `tone`, `model_config`, `is_public`).
   - GET `/api/v1/bots/public/{bot_id}` and assert `set(response.json().keys()) == {"id","slug","name","welcome_message","widget_config"}`.
   - Note: `PublicBotResponse` already enforces this via Pydantic model_dump; the test locks the contract.
2. Run `cd apps/api && uv run pytest tests/test_bot_router.py -k public -q` — green.
3. Commit: `test(api): lock public bot response to strict key allowlist`.

## Validation gate (run before push)

From the worktree root:

```bash
pnpm -C packages/widget test
pnpm -C packages/widget build
cd apps/api && uv run pytest -m unit -q --deselect tests/test_tenant_filter_audit.py::test_every_mongo_call_in_apps_api_is_tenant_scoped
```

Then sanity check the file scope:

```bash
git diff --name-only origin/main...HEAD
```

Should be (and only):

- `packages/widget/src/api.ts`
- `packages/widget/src/widget.ts`
- `packages/widget/src/index.ts`
- `packages/widget/src/config.ts`
- `packages/widget/src/publicBot.ts` (new)
- `packages/widget/src/types.ts` (only if `WidgetConfig` needs tweaks — try to avoid)
- `packages/widget/tests/*` (existing + new)
- `apps/api/tests/test_bot_router.py` (one new test)
- `docs/superpowers/specs/...md`, `docs/superpowers/plans/...md`

## Ship

`git push -u origin feat/86-widget-bot-id-and-public-config` then `gh pr create` per the runner instructions in the kickoff prompt.
