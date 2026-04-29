# /plan-feature — Feature Implementation Planner

Creates a detailed implementation plan for a feature. The plan must pass the "no prior knowledge" test — an engineer unfamiliar with the codebase can implement using only the plan.

## Arguments

- `$ARGUMENTS` — feature description OR GitHub issue number (e.g., `#42`)

## Process

### Phase 1: Feature Understanding

1. If an issue number is provided, read it: `gh issue view <number>`
2. If a description is provided, clarify:
   - What user-facing behavior should change?
   - What are the acceptance criteria?
   - Is this S/M/L/XL scope?
   - **Is this a design artifact or production code?** (see Phase 1.5)
3. For L/XL features, invoke brainstorming skill first
4. Write user stories in "As a [user], I want [action] so that [benefit]" format

### Phase 1.5: Deliverable-Type Routing (ask, don't guess)

This phase decides whether the feature is **production code**, a **design artifact**, or a **hybrid**. Do not silently keyword-match — load the canonical script and follow it.

**Reference:** `.claude/references/design-clarifying-script.md` — the canonical question script + routing matrix. Both `/start` and `/plan-feature` use the same source of truth.

**Process:**

1. **Detect project state** (run in parallel):
   - Fresh project: no UI files (`*.tsx`, `*.jsx`, `*.vue`, `*.svelte`) and no `package.json` → route directly to `/brand-extract` Direction Advisor; do NOT run this phase.
   - In-dev project: has UI files → continue.

2. **Decide whether to ask** by checking the "When the script runs" conditions in the reference:
   - **Skip the script** when intent is unambiguous (explicit `mockup`/`prototype`/`deck`/`slide`/`infographic`/`pitch`/`motion graphic` → design; explicit `bug fix`/`typo`/`endpoint`/`migration` or specific code-only issue → production).
   - **Run the script** otherwise. Most realistic in-dev requests fall here — that's expected.

3. **Run the 3-question script** verbatim from the reference. Send all three questions in one message; wait for all answers; don't dribble.

4. **Apply the routing matrix** (also in the reference) to deterministically map answers → plan branch.

5. **Write the plan with frontmatter** capturing the decision so `/execute` Step 2.5 can read it instead of re-classifying:

   ```yaml
   ---
   branch: design-artifact   # or production-code, or hybrid
   q1: b                      # answers from the clarifying script (omit if script was skipped)
   q2: a
   q3: a
   brand_spec: bootstrap     # or use-as-is, skip, or n/a
   ---
   ```

**Per-branch plan shapes:**

- **`production-code`** → continue to Phase 2 below as normal.
- **`design-artifact`** → single-task plan that dispatches huashu-design. Pre-step: verify `.design-system/brand-spec.md` per the chosen `brand_spec` mode (bootstrap = run `/brand-extract` as Task 0; use-as-is = run `/brand-extract --mode=codify-as-is`; skip = inline constraints only). Validation: `/validate` Phase 2.5 (5D Visual Critique). Skip the "tests before implementation" requirement — replace with tester-agent VERIFY screenshot + antislop checklist + 5D Critique.
- **`hybrid`** → emit **two plans**: (1) design-artifact plan first, (2) production-code plan that consumes the handoff bundle. The `bundle.json` is the contract.

**Anti-pattern guard:** if you find yourself reaching for a keyword list to decide, you're in script territory — ask. The script exists because keyword classifiers misroute "build a settings panel mockup that turns into a real component."

### Phase 2: Codebase Intelligence (Parallel Sub-Agents)

Launch 2-3 parallel sub-agents for speed:

**Agent 1 — Structure and Patterns:**
- Run `/prime` if not already primed
- Glob for files related to the feature
- Identify existing patterns (how similar features are built)
- Map the directory structure for relevant areas

**Agent 2 — Dependencies and Integration:**
- architect-agent RETRIEVE for relevant domains
- architect-agent IMPACT to understand what this change affects
- Identify integration points with other modules
- Check for shared utilities, types, or components to reuse

**Agent 3 — Testing and Validation:**
- Find existing test patterns for similar features
- Identify what test infrastructure exists
- Note validation commands (lint, type-check, test runners)

### Phase 3: External Research

- Use context7 MCP to verify framework APIs you plan to use
- Check library documentation for any unfamiliar APIs
- Note any dependencies that need to be installed

### Phase 4: Strategic Thinking

Before writing the plan, think through:
- Does this fit the existing architecture? If not, is refactoring needed first?
- What are the edge cases? (empty states, error states, concurrent access)
- Security implications? (input validation, auth checks, data exposure)
- Performance concerns? (N+1 queries, large payloads, unnecessary re-renders)
- What could go wrong during implementation?

### Phase 5: Plan Generation

Read `.claude/references/plan-template.md` and generate a complete plan.

Requirements for every plan:
- Exact file paths for every file to create or modify
- Complete code in every step (no placeholders)
- Exact terminal commands with expected output for every verification step
- TDD: tests before implementation in every task
- Conventional commit after every task
- GOTCHA warnings for known pitfalls
- Confidence score (1-10) for one-pass success

### Phase 6: GitHub Issue

If no issue exists for this feature:
```bash
gh issue create --title "[type]: description" --body "..." --label "feat,size:M"
```

If issue exists, add a comment linking to the plan:
```bash
gh issue comment <number> --body "Implementation plan: docs/plans/<plan-file>.md"
```

### Phase 7: Save and Offer Execution

Save to `docs/plans/<kebab-case-feature-name>.md`

Commit:
```bash
git add docs/plans/<plan-file>.md
git commit -m "docs: add implementation plan for <feature>"
```

Then offer:

> **Plan saved. Ready to implement?**
>
> For complex features (context reset recommended):
> Start a new session, run `/prime`, then `/execute docs/plans/<plan-file>.md`
>
> For simpler features (stay in session):
> Run `/execute docs/plans/<plan-file>.md`
