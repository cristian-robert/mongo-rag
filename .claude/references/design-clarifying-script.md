# Design-Path Clarifying Script

Loaded by `/start` Step 0.5 and `/plan-feature` Phase 1.5 whenever the project is **in active development** AND the user's request is ambiguous between production-code work and design-artifact work.

This file is the canonical script. Both commands reference it instead of duplicating the questions.

---

## When the script runs

### Run the script if ALL of these hold

1. The project is in-dev (has a `package.json`, `tailwind.config.*`, `app/` or `src/` with UI files, or any of `**/*.tsx`, `**/*.jsx`, `**/*.vue`, `**/*.svelte`).
2. The user's request matches **at least one** ambiguity signal:
   - Words: `redesign`, `refactor`, `rework`, `revamp`, `polish`, `clean up`, `improve`, `update`, `make better`
   - Mixed deliverable cues — request mentions both a UI surface (`page`, `screen`, `component`, `dashboard`, `flow`) AND a verb that could mean either ship-it or explore-it (`build`, `add`, `create`)
   - The phrase "design" or "look-and-feel" without a clear artifact word (`mockup`, `prototype`, `deck`)
3. There is no `.design-system/brand-spec.md` (or it's older than 90 days), OR no formal token system was detected (no `tailwind.config.*`, no CSS custom properties, no `components.json`).

### Skip the script (route silently) if

- The project is fresh (no UI files yet) → route to `/brand-extract` Direction Advisor branch
- Request is unambiguously a design artifact (explicit `mockup`, `prototype`, `deck`, `slide`, `infographic`, `pitch`, `motion graphic`, `MP4`, `GIF`)
- Request is unambiguously production code (explicit `bug fix`, `typo`, `failing test`, `endpoint`, `migration`, or references a specific issue with code-only acceptance criteria)
- A pre-existing plan file already declares `Branch: design-artifact` or `Branch: production-code` in its frontmatter

---

## The script (3 questions)

```
This project is in active development. Three quick questions before I plan:

1. What are you producing?
   a) Shippable UI in this codebase (production component, real route)
   b) A stakeholder artifact (mockup, prototype, deck, infographic) — not meant to ship
   c) Both — explore directions first, then implement the chosen one

2. What's the relationship to existing UI?
   a) Brand-new surface — no existing version to honor
   b) Refactor / redesign of an existing screen
   c) Small fix or tweak to existing UI (no exploration needed)

3. (Asked only if no .design-system/brand-spec.md exists OR no formal token system was detected)
   This project doesn't have a frozen design system. Three options:
   a) Bootstrap one now via /brand-extract (recommended — locks brand decisions before
      design work starts so output stays consistent and avoids codifying ad-hoc CSS)
   b) Use the existing codebase's de-facto patterns as-is (faster, but may codify
      inconsistencies as canonical — see warning below)
   c) Skip — I'll specify constraints inline in this plan only (one-off; no spec written)
```

**Warning to print verbatim above Q3 option (b):**

> If you pick (b) and the codebase mixes random hex codes, default Inter typography,
> or stock shadcn defaults, the brand-spec will codify those choices as canonical.
> Downstream design work will then dutifully reproduce them. This is the failure
> mode huashu-design's author warns about. Pick (a) if you have time; pick (c) for
> a one-off and revisit (a) later.

---

## Routing matrix (deterministic given answers)

Read the answers as `Q1.Q2.Q3` (Q3 omitted if not asked).

| Q1 | Q2 | Q3 | Route |
|---|---|---|---|
| **a** (shippable) | a / b | n/a or a / b | Production-code path. Existing `/plan-feature` Phase 2 onward. If brand-spec exists or Q3=a, use it. |
| **a** (shippable) | a / b | c (skip) | Production-code path with inline constraints in the plan only. No brand-spec written. |
| **a** (shippable) | c (small fix) | n/a (skip Q3 entirely) | Production-code path. Suppress all design detection in this plan. Treat as a normal bug-fix-shaped task. |
| **b** (artifact) | a / b / c | a (bootstrap) | `/brand-extract` (full extraction) → design-artifact plan → huashu-design → `/validate` Phase 2.5 |
| **b** (artifact) | a / b / c | b (use as-is) | `/brand-extract` (codify-as-is mode, with the warning recorded in `_extraction-log.md`) → design-artifact plan → huashu-design → `/validate` Phase 2.5 |
| **b** (artifact) | a / b / c | c (skip) | Design-artifact plan with inline constraints. No brand-spec written. huashu-design runs with constraints from the plan body. |
| **c** (hybrid) | a / b | a / b | Two-plan output: (1) design-artifact plan (via `/brand-extract` then huashu-design), (2) production-code plan that consumes the handoff bundle. The bundle is the contract between them. |
| **c** (hybrid) | a / b | c (skip) | Two-plan output as above, but constraints inline; no brand-spec written. |
| **c** (hybrid) | c (small fix) | n/a | Edge case — small fix shouldn't be hybrid. Push back on the user: "Q1=c (hybrid) and Q2=c (small fix) don't compose. Pick again." |

---

## Implementation notes for `/start` and `/plan-feature`

- **Detection runs BEFORE any other planning work.** Both commands check the conditions above as their first step (Step 0.5 in `/start`, Phase 1.5 in `/plan-feature`). If detection fires, ask all three questions in one message and wait for all answers — don't dribble one at a time.
- **Persist the answers** as plan frontmatter when a plan file is written:
  ```yaml
  ---
  branch: design-artifact   # or production-code, or hybrid
  q1: b
  q2: a
  q3: a
  brand_spec: bootstrap     # or use-as-is, or skip, or n/a
  ---
  ```
  This lets `/execute` Step 2.5 read the routing decision instead of re-classifying.
- **Don't keyword-classify silently** when these conditions are met. If you find yourself reaching for a word list to decide, you're in script territory — ask.
- **For fresh projects** (no UI files at all), skip this script entirely and route directly to `/brand-extract`'s Direction Advisor branch. The script assumes there's an existing codebase to ground decisions against.
