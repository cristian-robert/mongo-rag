---
title: testWebApp — Widget Test Host
tags: [tooling, widget, nextjs, dev]
type: feature
status: compiled
created: 2026-04-30
updated: 2026-05-02
sources:
  - sessions/2026-04-30-test-web-app-scaffold.md
related:
  - "[[feature-embeddable-widget]]"
---

# testWebApp — Widget Test Host

## Overview

`apps/testWebApp` is a third Next.js application in the monorepo (alongside `apps/web` and `apps/api`), running on **port 3101**. It exists for one purpose: serve a minimal, no-auth, no-CSP-nonce HTML page that hosts the embeddable chat widget bundle (`packages/widget/dist/widget.js`) so a developer can verify the widget loads and behaves correctly outside the customer dashboard. Think of it as a third-party-site simulator — the smallest possible page that matches what a paying customer's marketing site looks like when they paste the `<script>` snippet.

## Content

### Why a separate app at all

`apps/web` is the customer dashboard: it has Supabase auth, middleware, CSP nonces, and would conflate "is the widget broken?" with "is the dashboard broken?" when a regression appears. The standalone harness is intentionally minimal — a plain layout, no auth, no shared CSS, no React server components — so widget regressions surface in isolation. It also lets the widget team iterate without stomping on dashboard styles.

### Stack

Matches `apps/web` for parity but ships with no add-ons:

- Next.js 16.2.4
- React 19.2.4
- App Router
- Tailwind v4
- ESLint
- Turbopack
- TypeScript strict mode

Scaffolded via `pnpm create next-app@latest` — no shadcn, no Supabase, no auth wiring. The initial body is a placeholder Antikythera-mechanism editorial that will be replaced by the actual widget integration when the user wires it up.

### How to run

```bash
cd apps/testWebApp && pnpm install && pnpm dev   # → http://localhost:3101
```

The widget bundle is consumed via a `<script>` tag pointing at `packages/widget/dist/widget.js`. The integration step (creating the bot, configuring the script tag with the right `data-tenant-id` / `data-bot-id` / API key) is owned by the widget feature itself — see [[feature-embeddable-widget]] for that side.

### Key files

| File | Purpose |
|---|---|
| `apps/testWebApp/package.json` | `dev` and `start` scripts pin `--port 3101`. Package name is `test-web-app` (npm rejects capitals); the **folder** is camelCase to match `apps/web` / `apps/api` styling. |
| `apps/testWebApp/next.config.ts` | Sets `turbopack.root = __dirname` to silence the multi-lockfile workspace-root warning (see Gotcha 4). |
| `apps/testWebApp/app/{layout,page,globals.css}.tsx` | Placeholder editorial page — Fraunces serif headings, Geist body, parchment palette. To be replaced when the widget integration goes in. |

### Gotchas captured during scaffold

These are the specific failures hit while standing up the harness and the workarounds that resolved them. The first applies to *every* `create-next-app` invocation; the others are pnpm- or Turbopack-specific.

#### 1. Use the framework CLI, not hand-rolled config

The first attempt wrote `package.json`, `tsconfig.json`, `next.config.ts`, layout, and page by hand. The user corrected: *"why did you create files manually instead using cli"*. Switching to `pnpm create next-app@latest` produced a current-versions, current-conventions baseline in one command. This was internalized as user-level memory `feedback_use_cli_scaffolders.md` — for known frameworks, always prefer the official scaffolder.

#### 2. `create-next-app` rejects directory names with capital letters

`pnpm create next-app testWebApp` fails with *"name can no longer contain capital letters"*. The CLI derives the npm package name from the directory name and npm's package-name rules (lowercase only) reject it.

**Workaround:** scaffold into a lowercase dir, then rename the folder.

```bash
pnpm create next-app test-web-app
mv test-web-app testWebApp        # folder camelCase to match other apps
# package.json keeps "name": "test-web-app"
```

#### 3. After `mv`-ing a pnpm-installed directory, reinstall

pnpm stores packages under `node_modules/.pnpm/<pkg-name>/...` with **absolute paths** baked into the symlinks. After renaming the parent directory, those symlinks still point at the old absolute path, and Turbopack/Next dev throws errors like:

- `Can't resolve 'tailwindcss'`
- `Could not find the module ... in the React Client Manifest`

**Fix:** clear and reinstall in the renamed directory.

```bash
rm -rf node_modules .next && pnpm install
```

`curl localhost:3101` returns `HTTP 200` only after this step.

#### 4. Multi-lockfile Turbopack root warning

If a stray `package-lock.json` lives in `$HOME` (or any ancestor), Turbopack's auto-inferred workspace root jumps to the wrong directory and emits a "couldn't determine workspace root" warning. Pin it explicitly:

```ts
// apps/testWebApp/next.config.ts
import type { NextConfig } from "next";
const nextConfig: NextConfig = { turbopack: { root: __dirname } };
export default nextConfig;
```

`__dirname` works because `next.config.ts` is loaded as CJS — the scaffolded `package.json` has no `"type": "module"`.

#### 5. The frontend design-skill gate is for production UI, not dev tooling

While scaffolding, several plugin hooks injected "MANDATORY: run Skill(X)" prompts — `next-forge`, `next-cache-components`, `turbopack`, `shadcn`, `bootstrap`, `next-upgrade`, `env-vars`, `react-best-practices`, `verification`, plus the project's frontend design-skill gate. None applied to a placeholder dev-only test harness. Skipping them with one-line justifications was correct. The lesson: gates whose intent is "production customer-facing UI" (design-skill choice, antislop guardrails, brand-extract) should be skipped when the artifact is a dev tool. The frontend rule could be tightened to call this out explicitly.

## Key takeaways

- The harness exists to **isolate widget regressions** from dashboard regressions — keep it dumb, no auth, no shared CSS.
- For new apps in known frameworks, **use the official CLI** (`pnpm create next-app@latest`); never hand-roll `package.json` + config.
- `create-next-app` rejects capital letters in the directory name; **scaffold lowercase, then `mv`**.
- After **renaming a pnpm-installed directory**, run `rm -rf node_modules .next && pnpm install` — pnpm's symlinks are absolute-path-based and break on rename.
- A stray ancestor `package-lock.json` triggers a Turbopack workspace-root warning; **pin `turbopack.root = __dirname`** in `next.config.ts`.
- The **frontend design-skill gate is for prod UI**, not dev tooling — skip it for harnesses, scripts, and scaffolds with a one-line justification.

## Examples

### Minimal repro of the rename + install gotcha

```bash
pnpm create next-app test-web-app   # accept all defaults
cd test-web-app && pnpm install
mv ../test-web-app ../testWebApp    # rename ancestor
cd ../testWebApp && pnpm dev        # ❌ "Can't resolve 'tailwindcss'"

# Fix:
rm -rf node_modules .next && pnpm install
pnpm dev                            # ✅ HTTP 200 on :3101
```

### `next.config.ts` for the harness

```ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  turbopack: { root: __dirname },
};

export default nextConfig;
```

## See also

- [[feature-embeddable-widget]] — the artifact this app exists to test.
- `apps/testWebApp/CLAUDE.md` — local Claude Code rules for the harness (scaffolding-history aware).
- Auto-memory `feedback_use_cli_scaffolders.md` — the durable rule that came out of this session.
