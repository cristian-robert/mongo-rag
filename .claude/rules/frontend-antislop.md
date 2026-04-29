# Frontend Anti-AI-Slop Rules

Triggered alongside `.claude/rules/frontend.md` for any UI change.

## Skill Chain

1. Load catalogue: `.claude/references/frontend-antislop-patterns.md`
2. Load design skill (from frontend.md gate)
3. Cross-check component choices against the catalogue
4. tester-agent visual verify (antislop checklist mode)

## Conventions

- No Inter-everywhere typography; pair display + body face deliberately
- No purple→blue gradient defaults
- No emoji in primary CTAs
- No "✨ AI-powered" or equivalent copy
- Custom card borders — not default shadcn glow
- Motion has a purpose; honor `prefers-reduced-motion`
- **No CSS-silhouette stand-ins for real product imagery** — if a brand or product is named, use real assets (logo SVG, official renders, UI screenshots) per `.design-system/brand-spec.md`; never substitute hand-drawn SVG outlines or generic gradient blobs

## Checklist

- [ ] Typography pairing is intentional (not Inter/Inter)
- [ ] Color system is not default Tailwind gradient
- [ ] Components diverge from default shadcn look
- [ ] No AI-themed filler copy
- [ ] Motion is purposeful and respects reduced-motion
- [ ] If the work names a specific brand/product, real assets are used (no CSS silhouettes); brand-spec.md is up to date

## References

Load only when the rule triggers:

- `.claude/references/frontend-antislop-patterns.md` — full pattern catalogue with alternatives (always load when this rule triggers)
