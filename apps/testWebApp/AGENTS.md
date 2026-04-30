# apps/testWebApp — Widget Test Host

Standalone Next.js 16 (App Router, React 19, Tailwind v4) app on **port 3101**. Exists only to host `packages/widget/dist/widget.js` for manual end-to-end widget verification — no auth, no Supabase wiring. Body is currently a placeholder presentation page.

- Project conventions, design-skill gate, and library-doc protocol live in the root `CLAUDE.md` and `.claude/rules/frontend.md` — follow those.
- For Next.js / React API specifics, use the `context7` MCP (per `.claude/rules/frontend.md`), **not** the offline `node_modules/next/dist/docs/`.
- Module record: `[[tooling-test-web-app]]`.
- Pitfalls captured in `.claude/references/code-patterns.md` ("Scaffolding a New Frontend App").
