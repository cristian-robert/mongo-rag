# Frontend Anti-AI-Slop Patterns

Research-backed catalogue of design markers that signal AI-generated UI work, with approved alternatives. Compiled 2026-04-22.

This file is loaded by the `frontend` skill chain (and can be linked from design-gate prompts) so implementations avoid the "instantly recognizable as AI" aesthetic. Every anti-pattern bullet below is backed by at least one public source cited in the Sources section.

---

## Typography Defaults to Avoid

- **Inter everywhere** (especially Inter for both body and display) — called out as the default "AI fingerprint" typeface [1][2][3][4][5].
- **Roboto / Arial / default system-ui stack as the only fallback** — named alongside Inter as "safe, legible, and utterly forgettable" [2][5].
- **Monospace fonts used as decoration** for generic "hacker vibe" copy, without functional reason [4].

**Alternatives:** pair a distinctive display face with a neutral body. Practical pairings that ship across Linear, Vercel, and Stripe-style sites:

- Display: Fraunces, Instrument Serif, GT Sectra, Söhne Breit, PP Editorial New
- Body: IBM Plex Sans, General Sans, Söhne, Geist, Untitled Sans
- Mono (only where functional): JetBrains Mono, Berkeley Mono, Commit Mono

## Color Palette Anti-Patterns

- **Purple→blue gradients** (`from-purple-500 to-blue-500`, `from-indigo-500 to-violet-500`) — the single most-cited AI tell. Traced to Tailwind's early indigo/violet examples flooding training data [1][2][3][4][5].
- **Cyan-on-dark neon schemes** paired with glowing halos [4][5].
- **Gray text over colored/gradient backgrounds** — consistently cited as both an AI tell and an accessibility failure [4][5].
- **"Pastel everything"** — washed-out low-contrast cards floating on soft pastel voids [2].
- **Absolute `#000` on `#fff`** — flagged as lazy default contrast that ignores perceptual color science [5].

**Alternatives:**

- One committed accent hue + a neutral scale with **deliberate contrast tiers** (Refactoring UI's "scale of grays" principle: build a full 9–10 step gray scale and use it intentionally) [6][7].
- Prefer OKLCH over HSL/RGB so brand hue stays perceptually stable across light/dark [4].
- Off-black (`#0A0A0A`-ish) and off-white (`#FAFAFA`-ish) instead of pure black/white.

## Layout Anti-Patterns

- **Identical bento grids** on every landing page — the "same bento grid, same kinetic typography" critique [8].
- **Hero metric layout repeated verbatim:** big gradient number + small label + supporting stats + gradient accent [5].
- **"Three feature cards with icons below the fold"** — cookie-cutter grid that appears regardless of whether content fits it [1][3].
- **Cards nested in cards in cards** ("Cardocalypse") [4][5].
- **Glassmorphism floating in pastel voids** [2][5].

**Alternatives:**

- Composition driven by content, not templates. Start from the actual information hierarchy, not a grid preset.
- Asymmetric layouts that deliberately break the grid where the content earns it [4].
- Varied vertical rhythm — don't stamp the same section height down the page.

## Component Anti-Patterns

- **Default shadcn card + subtle shadow + rounded-lg on literally everything** — every Tailwind/shadcn app looking identical is a recognized complaint, not a strawman [9][3].
- **Rounded corners on every surface** at the same radius, regardless of context [1].
- **Subtle shadow at exactly `0.1` opacity** as the only depth cue [1].
- **Giant rounded Lucide icon centered above every heading** [5].
- **Thick colored border-rounded cards** [5].
- **Emoji in buttons** ("🚀 Get Started", "✨ Try it now") and **"AI-powered" sparkle copy** — universally cited AI copy tells [5][8].
- **Dot-grid background with radial fade** as a universal hero backdrop [2][5].

**Alternatives:**

- Custom border treatments (hairline borders, double borders, asymmetric radius, no radius at all on appropriate surfaces).
- Vary radius and elevation by component role — an input, a card, and a modal shouldn't all have the same radius/shadow.
- Content-first copy: write the CTA you'd say out loud, not the one with a rocket emoji.

## Brand Asset Anti-Patterns

When the deliverable names a specific brand or product, the assets you use to *represent* that brand carry as much slop signal as the colors and fonts. Backported from huashu-design's Core Asset Protocol [12].

- **CSS-silhouette / hand-drawn SVG stand-ins for real product photography** — the single biggest "generic AI tech animation" tell. Every brand looks identical when its product is rendered as a rounded-rect outline with a gradient fill. If the work names a real brand, use real assets.
- **Color palette + font extracted, but no logo / product render / UI screenshot** — branding without recognition. The recognizability ranking is: logo > product render > UI screenshot > color > font > vibe-keyword. Skipping the top three and only doing the bottom three is the modal AI failure mode.
- **Stock-photo placeholder where a real product image was findable** — usually means the agent didn't try `.com/press`, `.com/brand`, or YouTube launch-film frame extraction.
- **Mixed-quality assets** — pairing a 600px AppStore screenshot with a 3000px hero render. Visual cacophony reads as low-effort.

**Alternatives — the 5-10-2-8 quality gate (huashu-design):**

- **5** search rounds across distinct sources (official press kit, product page, official social, YouTube launch-film frames, Wikimedia, user-account screenshot if applicable) — not "first page of Google Images."
- **10** candidates collected before filtering — gives you something to reject from.
- **2** finals chosen — more than two competing hero images dilutes the composition.
- **8/10** minimum quality score per asset across: resolution (≥2000px, ≥3000px for print/big-screen), license clarity (official > public-domain > free-stock; suspected pirated = score 0), brand-vibe match, light/composition consistency with the other final, independent narrative role.

**Logo exception:** logos are not subject to 5-10-2-8 — they're a recognizability root, not a multi-choice. Use the official logo even if it's a 6/10 file; missing logo entirely is the failure mode.

**When you can't find an 8/10 asset:** use an honest placeholder (gray block + "{{ProductImage}}" label) or generate one with an AI image model using a real product photo as the conditioning reference. **Never substitute a hand-drawn CSS shape.** A gray block reads as "in progress"; a CSS silhouette reads as "AI couldn't be bothered."

**The frozen contract:** these decisions live in `.design-system/brand-spec.md`, which the project-level `/brand-extract` skill writes once and huashu-design reads on every invocation. Reasoning per huashu-design: "un-frozen knowledge evaporates" — the protocol exists because AI agents lose context between sessions; the spec persists.

## Motion Anti-Patterns

- **Marquee logos scrolling horizontally** on every landing page's "trusted by" section [10].
- **Scroll-triggered fade-in on every section** — flagged as "lazy or AI-feeling" when applied indiscriminately [11].
- **Bounce/elastic easing** on every micro-interaction [4][5].
- **Sparkline + gradient shimmer** as lazy "impact" animations [5].

**Alternatives:**

- Motion with purpose. Each animation must answer: what state change does this communicate?
- Ease-out-quart / ease-out-quint as defaults; reserve elastic for moments that earn it [4].
- Always respect `prefers-reduced-motion` — non-negotiable.

---

## Sources

1. [Why Your AI Keeps Building the Same Purple Gradient Website](https://prg.sh/ramblings/Why-Your-AI-Keeps-Building-the-Same-Purple-Gradient-Website) — accessed 2026-04-22 — catalogues Inter, purple/indigo gradients, 3-feature-card grids, rounded corners, `0.1` shadows as AI fingerprints.
2. [Why Your AI-Generated UI Looks Like Everyone Else's (And How to Break the Pattern)](https://medium.com/@Rythmuxdesigner/why-your-ai-generated-ui-looks-like-everyone-elses-and-how-to-break-the-pattern-7a3bf6b070be) — accessed 2026-04-22 — names Inter/Roboto, the purple-to-blue gradient as "the official color scheme of 'we used AI'", glassmorphism in pastel voids.
3. [Design Systems for AI Coding: Stop Getting Purple Gradients](https://www.braingrid.ai/blog/design-system-optimized-for-ai-coding) (Nico Acosta, 2025-12-08) — accessed 2026-04-22 — identifies purple gradients, Inter, rounded cards with subtle shadows as training-data defaults; recommends design tokens as antidote.
4. [The AI Slop Test — LinkedIn post](https://www.linkedin.com/posts/danwiner_the-ai-slop-test-if-someone-immediately-activity-7416821636450127872-NQhr) (Dan Winer) — accessed 2026-04-22 — full visual-red-flags list: cyan-on-dark, purple-blue gradients, neon accents, nested cards, Inter/Roboto/Arial, bounce/elastic easing; recommends OKLCH and ease-out-quart.
5. [AI Slop Design Tells — LinkedIn post](https://www.linkedin.com/posts/paulbakaus_ai-slop-design-tells-design-anti-patterns-activity-7416272383017164800-10DR) (Paul Bakaus) — accessed 2026-04-22 — deepest catalogue: Cardocalypse, giant Lucide icons above headings, thick colored border cards, hero metric layout template, glassmorphism/glow/neon as "lazy cool", gradients/sparklines/elastic as "lazy impact".
6. [Refactoring UI (homepage + tactics)](https://www.refactoringui.com/) (Adam Wathan & Steve Schoger) — accessed 2026-04-22 — foundational source for hierarchy via contrast, "scale of grays", deliberate color systems instead of defaults.
7. [12 Lessons for a better UI — Refactoring UI summary](https://medium.com/design-bootcamp/12-lessons-for-a-better-ui-refactoring-ui-the-book-c0e73b77d61d) — accessed 2026-04-22 — condenses Refactoring UI's hierarchy, gray-scale, and personality principles that directly counter flat AI defaults.
8. [Please Stop Designing Your Websites Like This](https://medium.com/write-a-catalyst/web-designs-are-so-cringe-now-18199cbc131c) — accessed 2026-04-22 — calls out same bento grid + same kinetic typography + sparkle-emoji copy as the "vibe coding" landing-page template.
9. [Is Anyone Else Tired of Every Tailwind/shadcn App Looking the Same?](https://www.designsystemscollective.com/is-anyone-else-tired-of-every-tailwind-shadcn-app-looking-the-same-69c545e73114) — accessed 2026-04-22 — enumerates shared shadcn aesthetic: same card, input, table, nav, button proportions across products.
10. [Dribbble — bento grid hero search](https://dribbble.com/search/bento-grid-hero-section) — accessed 2026-04-22 — evidence of bento-grid-hero saturation across thousands of recent designs, confirming the template fatigue critique.
11. [Reddit r/webdesign — Excessive scroll animation discussion](https://www.reddit.com/r/webdesign/comments/1rqsygf/what_do_you_think_about_the_excessive_scroll/) — accessed 2026-04-22 — designers naming scroll-triggered fade-in everywhere as a "lazy or AI-feeling" tell.
12. [alchaincyf/huashu-design SKILL.md (Core Asset Protocol)](https://github.com/alchaincyf/huashu-design/blob/master/SKILL.md) — accessed 2026-04-27 — source for the brand-asset recognizability ranking, the 5-10-2-8 quality gate, and the "no CSS silhouette" rule. A/B-tested with 6 agents, 5× variance reduction reported by author.

---

**How to use this file:** link to it from any frontend design prompt or skill chain. Before shipping UI, grep the diff for: `from-purple`, `to-blue`, `from-indigo`, `Inter`, `🚀`, `✨`, `AI-powered`, `bg-gradient`, default shadcn card imports used unchanged. If any appear, re-read the matching section above.
