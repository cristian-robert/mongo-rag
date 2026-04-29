---
description: Frontend development rules — Next.js / TypeScript / shadcn for the MongoRAG dashboard
globs: ["apps/web/**", "**/*.tsx", "**/*.jsx"]
paths:
  - "apps/web/**"
---

# Frontend Rules (Web)

## Design Skill Gate (MANDATORY)

**Step 0 — branch by deliverable type:**

- **Production app code** (React components, pages, routes, real shipping UI) → ask the 3-way question below
- **Design artifacts** (clickable HTML prototype, slide deck, motion piece, infographic, mockup, pitch one-pager) → use **`huashu-design`** (`npx skills add alchaincyf/huashu-design`). Pre-step: run `/brand-extract` if `.design-system/brand-spec.md` is missing.
- **Hybrid** (artifact → real implementation) → huashu-design first, then handoff bundle feeds `/execute` for production code.

**Step 1 — production-code 3-way (only when not using huashu-design):**

> "Which design approach should I use?"
>
> 1. **`/frontend-design`** — Full page/component creation with bold, distinctive aesthetics
> 2. **`/frontend-aesthetics`** — Lightweight design guardrails (typography, color, motion)
> 3. **`/ui-ux-pro-max`** — Design planning and exploration (50 styles, 21 palettes, font pairings)

`/frontend-aesthetics` combines with either other. Never combine `/frontend-design` + `/ui-ux-pro-max` — they conflict.

## Skill Chain

1. **KB search** — `KB_PATH=.obsidian node cli/kb-search.js search "<keywords>"` for relevant route/component articles
2. **architect-agent RETRIEVE** — understand page/component structure
3. **Design skill** — chosen via gate above
4. **shadcn MCP** — `search_items_in_registries`, `view_items_in_registries`, `get_item_examples_from_registries`, `get_add_command_for_items`, `get_audit_checklist`
5. **context7 MCP** — verify Next.js / React APIs before writing code
6. **tester-agent VERIFY/FLOW** — verify UI after implementation (NOT `/agent-browser`)
7. **KB update** — update wiki articles for new/changed routes, pages, components

## Frontend Skill Recipe

- Call `architect-agent` RETRIEVE/IMPACT before structural changes
- Ask user which design skill (gate above)
- Use `shadcn` MCP to check existing components first — never build custom when shadcn has it
- Load `/shadcn-ui` + `/vercel-react-best-practices` + `/nextjs-app-router-patterns` as needed
- Call `tester-agent` VERIFY/FLOW after changes
- **Superpowers Mode adds:** `/superpowers:brainstorming` first, `/superpowers:test-driven-development`, `/superpowers:verification-before-completion`

## Conventions

- Strict TypeScript, no `any` types
- Server components by default, client components only when needed
- Forms: React Hook Form + Zod validation
- State: prefer server state (React Query/SWR) over client state
- Styling: Tailwind + shadcn/ui primitives
- Accessibility: semantic HTML, ARIA labels, keyboard navigation
- Tests with the project's web test runner; `tester-agent` for E2E/visual

## Web Testing — Use `tester-agent`

After web frontend changes, use `tester-agent` (NOT `/agent-browser`) for verification:

- VERIFY for spot-checks: `VERIFY page:<path> Checks: <list>`
- FLOW for user journeys: `FLOW: <scenario> Steps: 1. ... 2. ...`
- Fix + re-run on FAIL

## Checklist

- [ ] Design skill gate answered before any UI creation
- [ ] tester-agent VERIFY/FLOW run after implementation
- [ ] Accessibility: keyboard nav + ARIA labels + semantic HTML
- [ ] Form inputs validated (Zod schema) with inline error surfaces
- [ ] No `any` types; no client component when a server component would do
- [ ] KB wiki articles updated for new/changed routes or components

## References

Load only when the rule triggers:

- `.claude/references/code-patterns.md` — server/client component patterns, API client
- `.claude/rules/frontend-antislop.md` — load for every UI change
- `.obsidian/wiki/_index.md` — search for existing route/component/feature articles before building
