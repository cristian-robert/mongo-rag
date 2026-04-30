---
title: testWebApp — Widget Test Host
tags: [tooling, widget, nextjs, dev]
type: feature
status: stub
created: 2026-04-30
updated: 2026-04-30
related: [[feature-embeddable-widget]]
---

# testWebApp — Widget Test Host

> Stub — expand during `/kb compile`. Source: `[[2026-04-30-test-web-app-scaffold]]`.

## What

`apps/testWebApp` — a third Next.js app in the monorepo, runs on **port 3101**, exists only to host a page that loads `packages/widget/dist/widget.js` for end-to-end manual verification of the embeddable chat widget.

## Why a separate app

`apps/web` is the customer dashboard: it has Supabase auth, middleware, CSP nonces, and would conflate "is the widget broken?" with "is the dashboard broken?". The standalone harness is the third-party-site simulator — minimal layout, no auth, no shared CSS — so a widget regression surfaces in isolation.

## Stack

Next 16.2.4 · React 19.2.4 · App Router · Tailwind v4 · ESLint · Turbopack · strict TS. Scaffolded via `pnpm create next-app@latest`. No shadcn, no Supabase, no auth.

## Run

```bash
cd apps/testWebApp && pnpm install && pnpm dev   # → http://localhost:3101
```

The widget bundle is consumed by the page via a `<script>` tag pointing at the bundle from `packages/widget/dist/widget.js` (integration handled by user; out of scope for the initial scaffold).

## Gotchas captured during scaffold

- `create-next-app` rejects capitalised directory names — scaffold into lowercase, then `mv` to camelCase.
- After `mv`-ing a pnpm-installed dir, run `pnpm install` again to rebuild absolute-path symlinks under `node_modules/.pnpm/`.
- A stray `~/package-lock.json` triggers a wrong-root Turbopack warning — pin with `turbopack: { root: __dirname }` in `next.config.ts`.

## Related

- [[feature-embeddable-widget]] — the artefact this app exists to test
