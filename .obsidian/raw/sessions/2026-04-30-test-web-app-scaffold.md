# Session: testWebApp scaffold + scaffolding gotchas (2026-04-30)

## What was built

`apps/testWebApp/` — a third Next.js app in the monorepo (alongside `apps/web`). Purpose: a developer-only host page on port 3101 used to verify the embeddable widget script (`packages/widget/dist/widget.js`) loads and behaves correctly when embedded in a third-party-site simulator.

Stack matches `apps/web`: Next 16.2.4, React 19.2.4, App Router, Tailwind v4, ESLint, Turbopack, TypeScript strict. Scaffolded with `pnpm create next-app@latest` (no shadcn, no Supabase wiring, no auth — it's a dumb test host).

Initial body of the page is placeholder: a one-page editorial presentation about the Antikythera Mechanism. Will be replaced when the actual widget integration goes in (user said they'd handle that part).

## Key files

- `apps/testWebApp/package.json` — `dev`/`start` use `--port 3101`; package name `test-web-app` (npm rejects caps; folder is camelCase but package name is hyphenated).
- `apps/testWebApp/next.config.ts` — sets `turbopack.root = __dirname` to silence the multi-lockfile workspace-root warning caused by a stray `~/package-lock.json`.
- `apps/testWebApp/app/{layout,page,globals.css}.tsx` — placeholder page with Fraunces serif headings + Geist body, parchment palette.

## Learnings

### 1. Use the framework CLI, not hand-rolled files

Started by writing `package.json`, `tsconfig.json`, `next.config.ts`, layout/page by hand. User corrected: "why did you create files manually instead using cli". Switched to `pnpm create next-app@latest` and got a current-versions, current-conventions baseline in one command. Saved as auto-memory `feedback_use_cli_scaffolders.md`.

### 2. `create-next-app` rejects directory names with capitals

`pnpm create next-app testWebApp` fails: *"name can no longer contain capital letters"* — it derives the npm package name from the directory name. Workaround that worked: scaffold into a lowercase dir (`test-web-app`), then `mv test-web-app testWebApp`. Package name in `package.json` stays `test-web-app`; only the folder is camelCase.

### 3. After `mv`-ing a pnpm-installed directory, reinstall

pnpm's `node_modules/.pnpm/<pkg>/...` entries use absolute paths internally. After renaming the parent directory the symlinks still point at the old absolute path, and Turbopack/Next dev throws *"Can't resolve 'tailwindcss' …"* and *"Could not find the module … in the React Client Manifest"*. Fix: `rm -rf node_modules .next && pnpm install` in the new directory. (Verifying with `curl localhost:3101` returned `HTTP 200` only after this step.)

### 4. Multi-lockfile turbopack root warning

If a stray `package-lock.json` lives in `$HOME` (or any ancestor), Turbopack's auto-inferred workspace root jumps up to the wrong directory and emits a warning. Pin it with:

```ts
// next.config.ts
import type { NextConfig } from "next";
const nextConfig: NextConfig = { turbopack: { root: __dirname } };
export default nextConfig;
```

`__dirname` works because `next.config.ts` is loaded as CJS (the scaffolded `package.json` has no `"type": "module"`).

### 5. Pragmatic skill-injection filtering

The session triggered a long stream of "MANDATORY: run Skill(X)" injections from the Vercel plugin and project rules — `next-forge`, `next-cache-components`, `turbopack`, `shadcn`, `bootstrap`, `next-upgrade`, `env-vars`, `react-best-practices`, `verification`, plus the frontend design-skill gate. None applied to a placeholder dev-only test harness. Skipped them with a one-line justification each. Worth a note in `frontend.md` rule that the design-skill gate is for *production customer-facing UI*, not dev tooling.

## Status

- ✅ App scaffolded, on port 3101, `HTTP 200`, page renders.
- ⏳ Widget script integration deferred — user handles.
- ⏳ Wiki stub: `tooling-test-web-app` (this entry will be expanded during `/kb compile`).
- ⏳ Architect-agent index.md needs an entry for the new module.
