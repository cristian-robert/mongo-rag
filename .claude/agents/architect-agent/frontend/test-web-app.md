# apps/testWebApp — Widget Integration Test Host

_Last verified: 2026-04-30_

## Purpose

Dev-only third-party-site simulator. Loads `packages/widget/dist/widget.js` so the embeddable chat widget can be manually verified end-to-end without coupling to `apps/web` (which has Supabase auth, CSP nonces, and shadcn).

## Files

- `apps/testWebApp/package.json` — name `test-web-app`; `dev`/`start` use `--port 3101`
- `apps/testWebApp/next.config.ts` — pins `turbopack.root = __dirname` (silences multi-lockfile warning)
- `apps/testWebApp/app/layout.tsx` — root layout; Fraunces serif + Geist body fonts
- `apps/testWebApp/app/page.tsx` — placeholder Antikythera-mechanism presentation page
- `apps/testWebApp/app/globals.css` — Tailwind v4 global styles

## Stack

- Next.js 16.2.4 (App Router, Turbopack), React 19.2.4, Tailwind v4, strict TS
- No auth, no Supabase, no shadcn

## Port

- Dev: **3101** (`next dev --port 3101`)

## Integrates With

- `packages/widget/` — loads `dist/widget.js` as a `<script>` tag (widget integration pending)
- `apps/api/` — widget talks to FastAPI at `NEXT_PUBLIC_API_URL` (port 8100)

## Watch Out

- Not in the CI pipeline — dev-only, no Docker image, no deploy target
- Folder name is camelCase (`testWebApp`); package name is kebab-case (`test-web-app`) — npm forbids capitals
- `turbopack.root = __dirname` required to avoid pnpm monorepo lockfile resolution warning in Next.js 16
- Do NOT add Supabase wiring here — that isolation is the point of this app
