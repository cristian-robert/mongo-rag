# Widget Theming Bundle — Design Spec

**Date:** 2026-05-04
**Branch:** `feat/widget-theming-bundle`
**Issues:** #87, #105, #88, #89 (closed in single PR; one commit per issue)
**Mode:** Superpowers

---

## Goal

Take the widget from "primary color + position" (current state) to a fully theme-able product that customers can preview live in the dashboard, install with one script tag, and trust to look distinctive — not generic AI slop. While the rendering work is in flight, also pay down the streaming UX gap (typing-state polish + chunk-soft-reveal + clean abort).

## Bundle scope (4 issues, one PR)

| Order | Commit | Issue | Layer |
|---|---|---|---|
| 1 | `feat(api): expand WidgetConfig with theme tokens` | #87 | apps/api |
| 2 | `feat(widget): SSE streaming UX polish (soft-reveal + abort)` | #105 | packages/widget |
| 3 | `feat(widget): render expanded theme tokens` | #88 | packages/widget |
| 4 | `feat(web): bot settings live preview + curated theme controls` | #89 | apps/web |

**Order rationale:** schema before consumers; streaming before rendering (small, independent change first while context is fresh); widget rendering before dashboard preview (preview iframe loads the widget bundle).

---

## Architecture

### Boundaries that don't move

- `Principal`-derived `tenant_id` everywhere. The bots router uses `core.authz.Principal` (dashboard JWT only); we keep it that way for this PR — migrating to `core.principal.Principal` is out of scope.
- `PublicBotResponse` stays an explicit allow-list. Every new field added in #87 must be re-asserted in `BotService.get_public`. A new pinned-allowlist test prevents future `model_dump()`-style leaks.
- Plan gate lives at the **route layer** (Q1). `apps/api/src/routers/bots.py` reads tenant plan from the existing Mongo `subscriptions` collection (already used by `BillingService` and `UsageService`); rejects `branding_text` writes for free tier with 403 before `BotService.update` is called.
- Preview transport: **URL-encoded JSON in iframe `?t=` param + reload on debounce 250ms** (Q2). No widget-side preview-mode flag. The widget gets one new public API: `MongoRAGWidget.bootWithConfig(config)`.
- Streaming transport (#105): **SSE via `fetch` + `ReadableStream`** (Q3). Already present in `packages/widget/src/api.ts` (`startChatStream`/`parseSSE`). This issue adds polish, not infrastructure.

### Single-source-of-truth font catalog

The curated font set is one TypeScript constant in `packages/widget/src/fonts.ts`:

```ts
export const WIDGET_FONTS = {
  system: { stack: 'ui-sans-serif, system-ui, ...', loader: null },
  inter: { stack: 'Inter, ui-sans-serif, system-ui, ...', loader: 'google:Inter' },
  geist: { stack: 'Geist, ui-sans-serif, system-ui, ...', loader: 'google:Geist' },
  'ibm-plex-sans': { stack: '"IBM Plex Sans", ui-sans-serif, ...', loader: 'google:IBM+Plex+Sans' },
  'work-sans': { stack: '"Work Sans", ui-sans-serif, ...', loader: 'google:Work+Sans' },
  fraunces: { stack: 'Fraunces, ui-serif, Georgia, serif', loader: 'google:Fraunces' },
  'jetbrains-mono': { stack: '"JetBrains Mono", ui-monospace, ...', loader: 'google:JetBrains+Mono' }
} as const;
export type WidgetFontKey = keyof typeof WIDGET_FONTS;
```

The Pydantic `Literal[...]` (#87) uses the same keys via a `BOT_FONTS` tuple in Python. A single conformance test (`apps/api/tests/unit/test_font_conformance.py`) regex-extracts keys from the TS file and asserts equality with `BOT_FONTS`. Single test catches drift across api/widget/dashboard.

### Font loading strategy (#88) — **scope-cut decision**

**Original spec (issue #88):** self-host woff2 inside the widget bundle, ≤60 KB gzipped budget.
**Decision:** lazy-load via Google Fonts CSS when `font_family !== "system"`. Inject one `<link rel="stylesheet">` into the Shadow DOM scoped to the active font(s). Reasons:

- 5 self-hosted woff2 + display weight = 200–400 KB even subsetted; busts the 60 KB target hard.
- Shipping a font-loader pipeline (subset, base64, lazy chunk) is meaningful unfunded work for an MVP feature.
- Google Fonts CSS lazy-load is one network request, ~5 KB, parallelizable, and customers familiar with the privacy tradeoff explicitly opt in by selecting non-system fonts.
- `prefers-reduced-data` skips the load entirely → falls back to the same stack with system fallback.
- Self-hosted woff2 can come back as a follow-up issue; the API surface (`font_family` Literal) is identical either way, so swapping the implementation later doesn't break the schema.

**Bundle size budget retained:** widget JS + CSS gzipped target ≤25 KB (was 15 KB, now 25 KB to absorb new tokens, dark-mode logic, soft-reveal). Fonts are out-of-bundle.

### Streaming UX (#105) — **rescoped from discovery**

SSE plumbing already exists. Remaining gaps:

1. **Soft-reveal cap inside chunks.** When `applyEvent` receives a `token` event with >12 chars of new content, don't paint it all in one frame. Schedule a `requestAnimationFrame` reveal at ~600 chars/sec. Skip under `prefers-reduced-motion`.
2. **Abort on new send.** Current code aborts only on widget destroy. Add: when a new `send()` fires while `state.abort` is non-null, abort the previous request first.
3. **Loading state polish.** Typing dots already exist but vanish on the first character (even one char). Add a 150 ms minimum dwell on the dots so single-char first deltas don't feel jarring. Honors reduced-motion.
4. **Error retry affordance.** On `event: error` or fetch failure, render the error bubble with a small inline "Retry" button that re-sends the last user message.

No transport changes. No new dependencies.

---

## Components & file inventory

### Backend (#87) — `apps/api/`

| File | Change |
|---|---|
| `src/models/bot.py` | Extend `WidgetConfig` (~25 new fields), add `WidgetDarkOverrides`, `BOT_FONTS` tuple, hex/url validators, `font_family`/`launcher_icon` Literals |
| `src/services/bot.py` | `get_public` rebuilt as explicit allow-list (no `model_dump()`); `_doc_to_response` carries new fields with safe defaults for legacy docs |
| `src/services/billing.py` | Add small `get_plan_tier(tenant_id) -> PlanTier` reader; reads `subscriptions` Mongo collection |
| `src/routers/bots.py` | New dependency `require_paid_plan_if_branding(payload, principal, billing_service)`; 403 with structured error if free-tier sets `branding_text` |
| `src/core/deps.py` | Expose a `get_billing_service()` DI factory for the gate dep (or compose inline) |
| `tests/unit/test_bot_models.py` | Hex regex (RGB+RGBA), HTTPS validator, `dark_overrides` warning behavior |
| `tests/unit/test_bot_public_payload.py` | Pin allow-list of fields in `PublicBotResponse` (snapshot-style) |
| `tests/unit/test_font_conformance.py` | Regex-extract `WIDGET_FONTS` keys from `packages/widget/src/fonts.ts`, assert equality with `BOT_FONTS` |
| `tests/integration/test_bots_branding_gate.py` | 403 path for free-tier `branding_text`, 200 path for paid |

### Widget — streaming polish (#105) — `packages/widget/`

| File | Change |
|---|---|
| `src/widget.ts` | Soft-reveal scheduler in `applyEvent` for `token` events; abort previous request on new `send`; 150 ms typing-dot dwell; retry affordance on error bubble |
| `src/widget.ts` (existing `applyEvent` export) | Wraps token text into a per-msg buffer; revealed via rAF cadence |
| `src/styles.ts` | Retry button class; reduced-motion overrides |
| `tests/widget-streaming.test.ts` | Soft-reveal pacing, reduced-motion bypass, abort-on-new-send |

### Widget — theme rendering (#88) — `packages/widget/`

| File | Change |
|---|---|
| `src/fonts.ts` (new) | Single source of truth: `WIDGET_FONTS` map + helpers (`fontStack`, `googleFontsUrl`) |
| `src/types.ts` | Extend `WidgetConfig` (and add `ThemeTokens` flat shape) to mirror Python model |
| `src/themeTokens.ts` (new) | Pure mapping `WidgetConfig → ThemeTokens` (radius/density/launcher/panel maps) + `applyDarkOverrides(base, dark)` |
| `src/styles.ts` | Token-driven `:host` CSS, `@media (prefers-color-scheme)` rules, font lazy-loader, density/radius/launcher maps, retry button |
| `src/widget.ts` | Avatar rendering in assistant bubbles, launcher icon variants (4 inline SVG + custom URL with fail-silent fallback), color-mode class on `:host`, `bootWithConfig` public API |
| `src/index.ts` | Export `bootWithConfig` on the global namespace |
| `src/publicBot.ts` | Extend `PublicBotConfig` typing + `mergePublicConfig` to thread new tokens |
| `src/config.ts` | Extend `RawConfigInput` for new tokens (data-* attribute parsing); maintain SAFE_COLOR validation; add `safeFont`, `safeRadius`, etc. |
| `tests/styles.test.ts` (new) | Snapshot tests on `buildStyles()` output for default + dark + branded combos |
| `tests/themeTokens.test.ts` (new) | Token resolver edge cases, dark-overrides merge |

### Dashboard (#89) — `apps/web/`

| File | Change |
|---|---|
| `app/(dashboard)/dashboard/bots/[id]/page.tsx` | Side-by-side layout: form (left, ~480px) + preview pane (right, sticky) |
| `app/(dashboard)/dashboard/bots/[id]/preview-frame/route.ts` (new) | Route handler returning HTML page that loads widget bundle, decodes `?t=` param, calls `bootWithConfig` |
| `app/(dashboard)/dashboard/bots/bot-form.tsx` | Refactor: extend sections (Color / Typography / Shape & Density / Branding), add live-preview-driving `useWatch`-based effect that posts a debounced URL update to the iframe |
| `app/(dashboard)/dashboard/bots/preview-pane.tsx` (new) | iframe wrapper, debounce, "Open fullscreen" link |
| `app/(dashboard)/dashboard/bots/presets.ts` (new) | 5 preset definitions (Default / Editorial / Soft minimal / Dark mono / Brutalist) |
| `app/(dashboard)/dashboard/bots/preset-row.tsx` (new) | 5 thumbnails with click-to-apply + single-step undo |
| `app/(dashboard)/dashboard/bots/anti-slop-warnings.tsx` (new) | Pure `evaluateWarnings(tokens) → Warning[]`, rendered inline per section |
| `app/(dashboard)/dashboard/bots/contrast.ts` (new) | WCAG ratio helper; AA/AAA labels |
| `lib/widget-fonts.ts` (new) | Re-export `WIDGET_FONTS` shape for the dashboard form |
| `lib/validations/bots.ts` | Extend `widgetConfigSchema` Zod schema to mirror new Pydantic fields |
| `lib/bots.ts` | Extend `WidgetConfig` interface for new fields |
| `tests/contrast.test.ts` (new) | WCAG AA ratio assertions on known pairs |
| `tests/anti-slop-warnings.test.ts` (new) | Each warning rule's trigger + non-trigger inputs |
| `public/widget.js` (symlink or copy) | Built widget bundle served from dashboard origin so the preview iframe can `<script src="/widget.js">` |

**Dashboard color picker** — no new deps. Use `<input type="color">` paired with a hex text input (already in current bot-form). Visible side-by-side in each color section.

**Dashboard slider/range** — `<input type="range">` styled with Tailwind `accent-foreground` (already used for temperature).

**Dashboard tooltip / warning aside** — small static `<aside>` with semi-muted styling, dismissible per session via `useState`.

---

## Data flow

### Theme write
```
Dashboard form → Zod (#89) → server action → PUT /api/v1/bots/{id}
  → routers/bots.py: require_role(ADMIN) + require_paid_plan_if_branding
  → BotService.update → Mongo upsert
```

### Widget runtime read (production)
```
Widget boot → GET /api/v1/bots/public/{id}
  → BotService.get_public → explicit allow-list build
  → widget receives full WidgetConfig (system_prompt etc. stripped)
  → buildStyles(tokens) injects token-driven CSS
  → render() consumes tokens (font stack, radii, dimensions, color mode class)
```

### Preview read (unsaved tokens)
```
bot-form.tsx onChange (debounced 250ms)
  → encodeURIComponent(JSON.stringify(draft))
  → iframe.src = "/dashboard/bots/{id}/preview-frame?t=…"
  → preview-frame/route.ts: parse ?t= via Zod, render HTML with
      <script src="/widget.js" data-preview-tokens='…'></script>
  → widget index.ts detects data-preview-tokens, calls bootWithConfig(tokens)
  → preview iframe shows live look; chat input is disabled
```

### Streaming (#105)
```
POST /chat (Accept: text/event-stream)
  → fetch + ReadableStream → parseSSE
  → applyEvent({type:'token', content:Δ}, msg)
  → if Δ.length > 12 and !reducedMotion: rAF reveal at ~600 cps
    else: paint immediately
  → on 'done': pending=false, citations rendered
  → on 'error': retry button rendered
  → on new send while state.abort: state.abort.abort() first
```

---

## Error handling

| Layer | Failure | Behavior |
|---|---|---|
| API #87 | Hex validation fails | Pydantic 422 with field path |
| API #87 | Free tier sets `branding_text` | 403 `{detail: "branding_text requires a paid plan"}` |
| API #87 | `dark_overrides` set with `color_mode == "light"` | Accepted, logged at INFO ("dead config"), not an error |
| Widget #105 | Malformed SSE event | `tryParseJson` returns null → skipped, stream continues |
| Widget #105 | Network error mid-stream | error bubble + retry button (re-sends last user message) |
| Widget #105 | Abort | Silent cleanup; no DOM mutation post-abort |
| Widget #88 | Avatar URL fails to load | Neutral colored circle with bot-name initial fallback |
| Widget #88 | Custom launcher icon URL fails | Falls back to default `chat` SVG |
| Widget #88 | Public config fetch fails | Widget keeps default tokens, doesn't break |
| Dashboard #89 | Token decode fails on preview frame | Render with defaults, log warning |
| Dashboard #89 | iframe load error | "Preview unavailable — save and reload" placeholder |
| Dashboard #89 | Anti-slop warning triggers | Inline `<aside>`, dismissible, never blocks save |

---

## Testing strategy

**Per superpowers TDD:** tests-first for high-risk pieces (validators, public-payload boundary, SSE soft-reveal scheduler, plan-gate, font conformance). Pragmatic test-after for visual/CSS where snapshot tests are sufficient.

| Layer | Tooling | High-risk tests (TDD) | Polish tests (test-after) |
|---|---|---|---|
| API #87 | pytest | hex/URL validators, public-payload pin, plan-gate 403, font conformance | model defaults, CRUD round-trip |
| Widget #105 | vitest+happy-dom | soft-reveal cadence, reduced-motion bypass, abort-on-new-send | typing-dot dwell timing |
| Widget #88 | vitest | dark overrides resolver, token mapping | snapshot of buildStyles for 3 themes |
| Dashboard #89 | vitest | contrast ratio (WCAG AA/AAA), anti-slop warning rule triggers | preset apply + undo |
| Bundle E2E | tester-agent on testWebApp:3101 (if running) or skipped with note | Default theme renders, dark mode toggles, streaming + soft-reveal, preview reflects form changes |

**No live tester-agent run if dashboard/api dev servers aren't already up** — autonomous mode constraint. Tests will document expected behavior and live verification is owner's job on next session, OR I'll attempt to start servers and run tester-agent if feasible.

---

## Out of scope (explicit)

- Self-hosted woff2 fonts (deferred — use Google Fonts CSS for now)
- Server-side preset library (presets are static dashboard data)
- Theme JSON import/export
- Per-conversation theme overrides
- A/B testing infrastructure for themes
- WebSocket transport for streaming (`/chat/ws?ticket=` exists but unused)
- Migration of `core.authz.Principal` callers to `core.principal.Principal`
- Custom raw-CSS escape hatch (security surface too large)

## Acceptance — bundle level

- All four issues' acceptance criteria met (see issue bodies; deltas captured in this spec for the streaming-already-wired discovery and the font-hosting decision)
- `uv run pytest` green; `uv run ruff check .` and `uv run ruff format --check .` clean
- `pnpm --filter @mongorag/widget test` green; `pnpm --filter @mongorag/widget typecheck` clean
- `pnpm --filter web lint` and `pnpm --filter web build` clean
- KB wiki updates: extend `feature-bot-configuration.md` + `feature-embeddable-widget.md`; create `feature-widget-theming.md`
- Architect-agent RECORD called once at the end with cross-cutting summary
- PR opens against `main`, `Closes #87 #105 #88 #89`
