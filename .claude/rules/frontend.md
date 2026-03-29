---
paths:
  - "apps/web/**"
---

# Frontend (Web) Development Rules

## Design Skill Gate — ASK BEFORE LOADING

**MANDATORY:** Before ANY web UI creation work, ask the user which design skill to load:

> "Which design approach should I use?"
>
> 1. **`/frontend-design`** — Full page/component creation with bold, distinctive aesthetics
> 2. **`/frontend-aesthetics`** — Lightweight design guardrails (typography, color, motion)
> 3. **`/ui-ux-pro-max`** — Design planning and exploration (50 styles, 21 palettes, font pairings)

- `/frontend-aesthetics` can combine with either of the other two
- Never combine `/frontend-design` + `/ui-ux-pro-max` — they conflict

## shadcn MCP — Check Before Building Custom Components

Use `shadcn` MCP tools to check what's available BEFORE building custom components:

- `search_items_in_registries` — find components by name or description
- `view_items_in_registries` — read component source code and variants
- `get_item_examples_from_registries` — get real usage examples
- `get_add_command_for_items` — get the exact install command
- `get_audit_checklist` — audit shadcn setup for issues

## Web Testing — Use `tester-agent`

After web frontend changes, use `tester-agent` (NOT `/agent-browser`) for verification:

- VERIFY for spot-checks: `VERIFY page:<path> Checks: <list>`
- FLOW for user journeys: `FLOW: <scenario> Steps: 1. ... 2. ...`
- Fix + re-run on FAIL

## Frontend Skill Recipe

- Call `architect-agent` RETRIEVE/IMPACT before structural changes
- Ask user which design skill (see gate above)
- Use `shadcn` MCP to check existing components first
- Load `/shadcn-ui` + `/vercel-react-best-practices` + `/nextjs-app-router-patterns` as needed
- Call `tester-agent` VERIFY/FLOW after changes
- **Superpowers Mode adds:** `/superpowers:brainstorming` first, `/superpowers:test-driven-development`, `/superpowers:verification-before-completion`
