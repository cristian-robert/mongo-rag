---
name: brand-extract
description: Extracts brand assets (logo, product imagery, UI screenshots, color/typography tokens) from a project's codebase plus official brand channels, then freezes them into `.design-system/brand-spec.md` so design-artifact skills (huashu-design, frontend-design, etc.) read the same canonical spec on every run instead of asking the user from scratch. Triggers on requests to set up the brand system, capture brand assets, prepare brand-spec.md, onboard a project for design work, or run before huashu-design when no brand-spec exists. Project-state-aware (fresh / token-driven / ad-hoc) — runs the Direction Advisor for fresh projects and refuses silent codification of slop. Implements huashu-design's Core Asset Protocol with budget caps, an independent quality-scoring subagent, and a staleness check.
---

# /brand-extract — Project Brand Asset Extraction

Writes the canonical `.design-system/brand-spec.md` for a project so downstream design skills (huashu-design, frontend-design, frontend-aesthetics) reuse it instead of re-asking the user. Implements huashu-design's Core Asset Protocol.

The skill's contract: **assets > spec.** Brand recognizability ranks logo > product render > UI screenshot > color > font > vibe-keyword. We capture all six, in that priority order — but the *path* depends on project state.

## Modes

| Invocation | Behavior |
|---|---|
| `/brand-extract` (default) | Run the full protocol with quality gating |
| `/brand-extract --mode=codify-as-is` | Skip quality gating; codify the project's existing patterns even if they're ad-hoc. Used when the operator explicitly accepts the codify-existing-slop tradeoff. |
| `/brand-extract --mode=refresh` | Re-run extraction; overwrite existing spec but keep human-edited sections marked `<!-- preserve -->` |
| `/brand-extract --mode=append` | Add new asset categories without touching existing entries |

## When to Use

- Before any design-artifact work where `.design-system/brand-spec.md` is missing
- When the user explicitly asks to "set up the brand system" or "extract brand assets"
- As Task 0 of a `/plan-feature` design-artifact plan (auto-invoked by `/execute` Step 2.5)
- When the user says the project's existing brand-spec is stale and needs a refresh
- When `/start` Step 0.5 routes a fresh project here for direction-advisor bootstrapping

## When NOT to Use

- The deliverable is generic with no specific brand named — skip; let the design skill's design-direction advisor work from inline constraints
- The change is to existing app code that already follows project conventions — `/brand-extract` is for kicking off design artifacts, not auditing production CSS

## Process

### Phase 0: Fact Verification (Principle #0, huashu-design)

If the user named a specific product/version/release, verify it exists before extracting anything.

1. Run `WebSearch` (or the `firecrawl search` skill) for `<product> 2026 latest release specs`
2. Read 1–3 authoritative results
3. Confirm: existence, release status, current version, key specs
4. Write findings to `.design-system/product-facts.md`

**Banned phrases until you've searched:**
- "I think X is at version N"
- "X probably hasn't shipped yet"
- "X likely doesn't exist"

A 10-second search prevents the hour-of-rework "DJI Pocket 4 unreleased" failure mode.

### Phase 0.5: Project-State Classifier (decides Phase 2 path)

Run these checks in parallel and classify the project into one of three states.

```bash
# Codebase signal
test -f tailwind.config.ts -o -f tailwind.config.js -o -f tailwind.config.mjs && echo TOKEN_TAILWIND
test -f components.json && echo SHADCN
grep -rE '^[[:space:]]*--[a-z][a-z0-9-]*:' app/globals.css src/styles/*.css 2>/dev/null | head -1 && echo TOKEN_CSSVARS
test -f theme.json -o -f .design-system/tokens.json && echo TOKEN_FILE
find . -maxdepth 4 -name '*.tsx' -o -name '*.jsx' -o -name '*.vue' -o -name '*.svelte' 2>/dev/null | head -1 && echo HAS_UI
find . -maxdepth 2 -name 'package.json' 2>/dev/null | head -1 && echo HAS_PKG
```

Classify:

- **fresh** — no UI files AND (no `package.json` OR a brand-new one with no UI deps).
- **token-driven** — has UI files AND any of `TOKEN_TAILWIND` / `SHADCN` / `TOKEN_CSSVARS` / `TOKEN_FILE`.
- **ad-hoc** — has UI files but no token signal: random hex codes scattered, no Tailwind config, no CSS variables, no shadcn theme.

Branch behavior:

| State | Behavior |
|---|---|
| **fresh** | Skip Phases 1–6. Run **Phase 0.6 Direction Advisor** instead. Spec gets bootstrapped from a chosen design direction, not extracted. |
| **token-driven** | Run Phases 1–6 normally — extraction works as designed. |
| **ad-hoc** | **Stop and ask.** Print the warning below; require user choice (`bootstrap` / `codify-as-is` / `cancel`). Default mode = stop. |

**Ad-hoc warning (print verbatim):**

> This project has no formal design system: no Tailwind config / no CSS custom properties /
> no shadcn theme. Extracting "brand tokens" from ad-hoc CSS will codify the existing
> defaults (likely Inter typography, indigo or purple gradients, default shadcn radii)
> as the project's canonical brand. This is the failure mode huashu-design's author
> warns about explicitly: bad source = bad output, frozen forever.
>
> Three options:
>   1. bootstrap        — Run the Direction Advisor (Phase 0.6) to pick a design
>                         direction first, then this skill writes a coherent spec.
>                         Recommended.
>   2. codify-as-is     — Re-run with `--mode=codify-as-is` to codify whatever the
>                         project currently uses. Spec will record this in
>                         `_extraction-log.md` so reviewers see the choice. Use only
>                         if the project genuinely owns its current ad-hoc style and
>                         wants to keep it.
>   3. cancel           — Don't write a spec. Use inline constraints in the next
>                         design-artifact plan instead.

### Phase 0.6: Direction Advisor (fresh projects only — huashu-design pattern)

For fresh projects, there's nothing to extract. Bootstrap a direction first.

1. Skill prompt summary: "This project has no existing UI to ground brand decisions in. Pick a design direction so downstream artifacts have a coherent point of view."
2. Recommend **3 differentiated directions** drawn from huashu-design's catalogue (5 schools × 20 philosophies). At least one each from distinct schools (Pentagram-style information architecture, Field.io-style motion, Kenya Hara-style restraint, Sagmeister-style experimentation, etc.). Each comes with: representative designer/studio, gestalt keywords, typography pairing, palette family.
3. If huashu-design is installed, dispatch it with `MODE=advisor` and pass the user's brief; let huashu-design generate three preview HTMLs in parallel under `.design-system/directions/{1,2,3}/preview.html`. If huashu-design isn't available, just describe the three directions in chat and ask the user to pick.
4. User picks one (`1`, `2`, or `3`).
5. Continue to Phase 6 with the chosen direction's tokens + vibe as the spec source. Skip Phases 2–5 — there's no codebase to extract from.

### Phase 1: Check Existing State

```bash
ls -la .design-system/ 2>/dev/null
```

- If `.design-system/brand-spec.md` exists → read its `Generated:` date.
  - Older than 90 days OR newer commits exist on `tailwind.config.*` / `app/globals.css` / `src/styles/**` / `components/ui/**` → warn but proceed; let the user choose `--mode=refresh` if they want to rebuild.
  - Default to `--mode=append` if existing spec is fresh and the user only wants to add categories.
  - Never overwrite silently.
- If absent → bootstrap the directory:
  ```bash
  mkdir -p .design-system/assets .design-system/refs
  ```

### Phase 2: Codebase Discovery (parallel, token-driven path only)

Three independent searches:

**a. Token sources**
- `tailwind.config.{ts,js,mjs}`
- `app/globals.css`, `src/styles/*.css`, `theme.css`
- `components.json` (shadcn) → walk `components/ui/*`
- CSS custom properties in `:root { --... }`

**b. Existing brand assets in repo**
- `public/logo*`, `public/brand/*`, `public/images/logo*`
- `.svg` files referenced from layout/header components
- `og-image*`, social share graphics

**c. Project metadata**
- `package.json` → name, description, homepage
- `README.md` → identify brand voice/tone signal
- Existing marketing pages (e.g., `app/(marketing)/page.tsx`) → screenshot for vibe extraction

Write findings to `.design-system/_extraction-log.md`.

### Phase 3: Ask the 6-Asset Checklist (one batch)

Send the full list, wait for all answers — don't dribble.

```
For brand <name>, which of these do you have? Priority order:

1. Logo (SVG or high-res PNG) — REQUIRED for any brand
2. Product photography / official renders — REQUIRED for physical products
3. UI screenshots / interface assets — REQUIRED for digital products
4. Color palette (HEX / RGB / brand swatches)
5. Typography (display / body fonts)
6. Brand guidelines PDF / Figma design system / brand site URL

For each: send what you have, or say "search for it" and I'll go find it.
```

If the user says "I don't know, you decide" → proceed to Phase 4 with `<brand>` defaulted to the project name from `package.json`.

### Phase 4: Search Official Channels (asset-by-asset, BUDGETED)

**Hard fetch budget: 30 fetches per `/brand-extract` invocation.** Track in `.design-system/_extraction-log.md` under a `Fetches:` running counter. When the budget hits 25 (warn) and 30 (stop), halt searching and use placeholders for any unfilled asset slot.

Cache by URL hash:

```bash
# Cache key example
hash=$(printf '%s' "$url" | shasum -a 256 | awk '{print $1}')
cache=".design-system/refs/.cache/$hash"
[ -f "$cache" ] || curl -A "Mozilla/5.0" -L "$url" -o "$cache"
```

Refuse re-fetching the same URL within a single invocation — count cache hits separately and don't charge them against the budget.

For every missing asset, three fallback paths in order:

| Asset | Search paths (in priority order) |
|---|---|
| **Logo** | `<brand>.com/brand` → `<brand>.com/press` → inline SVG from `<brand>.com` HTML → official social avatar |
| **Product render** | `<brand>.com/<product>` hero image → `<brand>.com/press` press kit → official YouTube launch-film frames (`yt-dlp` + `ffmpeg`) → Wikimedia Commons → AI-generated using a real product photo as reference (never CSS silhouette) |
| **UI screenshot** | App Store / Google Play screenshots → official site `screenshots/` section → product demo video frames → official social posts at version-launch dates |
| **Color palette** | inline CSS on official site → Tailwind config in their public repos → brand guidelines PDF |
| **Typography** | `<link>` tags on official site → tracked Google Fonts requests → brand guidelines |
| **Vibe keywords** | descriptive phrases from official press copy + tagline + hero headline |

Cache assets under `.design-system/assets/<brand>/`.

### Phase 5: Independent Quality Scoring (NOT self-scored)

5-10-2-8 enforcement happens in a **separate scoring subagent** so the agent extracting and using the assets isn't the same one judging quality. This addresses the "agent grades its own homework" failure mode.

**Process:**

1. After Phase 4 collects candidates per asset type, **dispatch a scoring subagent** with `MODE=asset-quality-scorer`. Pass:
   - The candidate URLs (with file hashes) for each asset slot
   - The vibe keywords from Phase 3
   - The 5-10-2-8 rubric (below)
   - Explicitly **do NOT tell the scorer which agent collected the candidates or which artifact will use them.** The scoring subagent should not know it's gating its own caller's downstream work.
2. Scorer returns scores + verdict per asset slot:

   ```
   asset_slot: product_hero
   candidates:
     - url_hash: a1b2... resolution: 3200x2400  license: official    score: 9/10
     - url_hash: c3d4... resolution: 1024x768   license: stock-free  score: 6/10  (REJECT)
     ...
   selected: [a1b2..., e5f6...]   # the two finals
   placeholders_needed: 0
   ```
3. **Programmatic dedup** before scoring: hash candidate URLs and reject duplicates; require at least 5 distinct hashes per asset before scoring runs. If fewer, mark the slot as `INSUFFICIENT_CANDIDATES` and use a placeholder.

**5-10-2-8 rubric (passed to scorer):**

- **5** search rounds across distinct sources
- **10** distinct candidates collected (hashed; duplicates rejected programmatically)
- **2** finals chosen
- **8/10** minimum across:
  1. Resolution — ≥ 2000px (≥ 3000px for print/big-screen)
  2. License clarity — official > public-domain > free-stock; suspected pirated = 0
  3. Brand-vibe match — agrees with the vibe keywords
  4. Light/composition consistency with the other final
  5. Independent narrative role — earns its place, not decoration

**Logo exception:** logos are not subject to 5-10-2-8 — recognizability root, not multi-choice. Use the official logo even if it's a 6/10 file; missing logo is the failure mode.

**Below-8/10 fallback:** use an honest gray-block placeholder (`{{ProductImage}}`) or AI-generate using a real reference. **Never** substitute a hand-drawn CSS silhouette.

Record scores in `.design-system/_quality-log.md`.

### Phase 6: Write `brand-spec.md`

Use this exact schema. The required sections (`Identity`, `Assets`, `Tokens`, `Anti-fingerprints`) match `.claude/.versions.json#schema_contract` so `/setup` can verify schema compliance after a huashu-design upgrade.

```markdown
---
generated: <ISO date>
generator: /brand-extract
mode: bootstrap | codify-as-is | refresh | append | direction-advisor-fresh
project_state: fresh | token-driven | ad-hoc
direction_picked: <1 | 2 | 3 | n/a>   # only set when project_state=fresh
---

# Brand Spec — <project name>

> Re-run /brand-extract to refresh. Manual edits between `<!-- preserve -->`
> markers survive `--mode=refresh`.

## Identity

- **Name:** <project / brand name>
- **Tagline:** <one sentence>
- **Vibe keywords:** <3–6 words: "warm-natural", "premium-restrained", etc.>
- **Voice / tone:** <2 sentences extracted from README + marketing copy>
- **Audience:** <who reads / uses this>

## Assets (priority order)

### Logo (REQUIRED)
- Primary SVG: `.design-system/assets/<brand>/logo.svg`
- Inverted (for dark bg): `.design-system/assets/<brand>/logo-white.svg`
- Notes: <usage rules — clear-space, min-size, color variants>

### Product imagery
- Hero render: `.design-system/assets/<brand>/product-hero.png` — score: N/10
- Secondary: `.design-system/assets/<brand>/product-detail.png` — score: N/10
- Source: <URL>
- Notes: <when to use which>

### UI screenshots (digital products)
- Primary screen: `.design-system/assets/<brand>/ui-primary.png` — score: N/10
- Secondary: `.design-system/assets/<brand>/ui-secondary.png` — score: N/10
- Source: <URL or "user-supplied">

## Tokens (OKLCH preferred)

```css
:root {
  --brand-primary: oklch(...);
  --brand-accent: oklch(...);
  --neutral-fg: oklch(...);
  --neutral-bg: oklch(...);
  /* full scale */
}
```

### Typography
- Display: `<font-family>` — license: <Google Fonts / commercial / system>
- Body: `<font-family>`
- Mono (only where functional): `<font-family>`
- Pairing rationale: <one sentence — why this combo, not Inter/Inter>

### Spacing scale
4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 (or project-specific)

### Radii
<role → value mapping; vary by role>

## Anti-fingerprints (project-specific)

What this project must NOT look like. Auto-extracted from existing codebase + the
catalogue in `.claude/references/frontend-antislop-patterns.md`:

- <e.g. "existing marketing site uses indigo→violet gradient — new work must NOT reproduce">
- <e.g. "competitor X uses bento-grid hero — avoid">
- <e.g. "no CSS-silhouette stand-ins — see brand-spec product imagery for the real renders">

## Sources

- Logo: <URL + access date>
- Product hero: <URL + access date>
- UI screenshots: <URL or "user-supplied" + date>
- Color extraction: <URL or commit ref>
- Typography: <URL>

## Quality log

See `_quality-log.md` for per-asset 5-10-2-8 scores from the scoring subagent.

## Refresh policy

This spec is canonical until /brand-extract is re-run. Manual edits between
`<!-- preserve -->` markers survive `--mode=refresh`.

If `git log --since=<generated>` shows changes to `tailwind.config.*` /
`app/globals.css` / `src/styles/**` / `components/ui/**`, the spec may be stale —
re-run /brand-extract.
```

### Phase 7: Stage (do NOT commit)

The framework's mandatory rule: **all commits go through `/commit`.** This skill stages files and tells the user to invoke `/commit` themselves.

```bash
git add .design-system/
```

Then tell the user:

```
Staged .design-system/ for commit. Run /commit to create the commit, or
/commit-push-pr if you want to push and open a PR.

Suggested message (you can override in /commit):

  feat(brand): extract brand spec for <name>

  - Logo, product imagery, UI screenshots captured per Core Asset Protocol
  - Tokens expressed in OKLCH
  - Anti-fingerprints listed for downstream design skills
  - 5-10-2-8 quality scores logged (independent scoring subagent)
  - project_state: <fresh|token-driven|ad-hoc>, mode: <...>
```

If KB is configured (`CLAUDE.md` has a `## Knowledge Base` section with a `Path:` value), suggest:

```
After /commit, run /kb ingest .design-system/brand-spec.md to make the spec
searchable from /prime and /execute.
```

## Output Summary

Tell the user:

```
Brand spec written to .design-system/brand-spec.md
- Project state: <fresh | token-driven | ad-hoc>
- Mode: <bootstrap | codify-as-is | refresh | append | direction-advisor-fresh>
- Logo: ✓ / ✗ (placeholder)
- Product imagery: N/2 finals at ≥8/10 (independent scoring subagent)
- UI screenshots: N/2 finals at ≥8/10 (independent scoring subagent)
- Tokens: OKLCH + type scale + spacing
- Anti-fingerprints: N project-specific rules
- Fetches used: N / 30
- Cache hits: M

Files staged. Run /commit to create the commit.

Downstream skills (huashu-design, /frontend-design, /frontend-aesthetics) will now
auto-load this spec instead of asking from scratch.
```

## References

Load only when the rule triggers:

- `.claude/references/frontend-antislop-patterns.md` — Brand Asset Anti-Patterns section, 5-10-2-8 details, sources
- `.claude/rules/frontend-antislop.md` — checklist used in pre-write lint
- `.claude/rules/frontend.md` — the design-skill gate that consumes this spec
- `.claude/references/design-clarifying-script.md` — the routing script that decides whether `/brand-extract` runs at all
- `.claude/.versions.json` — pinned huashu-design version + brand-spec schema_contract
