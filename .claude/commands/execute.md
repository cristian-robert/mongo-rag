# /execute — Plan Executor

Executes an implementation plan task by task with TDD discipline.

## Arguments

- `$ARGUMENTS` — path to plan file (auto-detected from current branch if omitted)

## Prerequisites

- A plan file must exist
- If the plan specifies dependencies to install, install them first
- Read the plan's "Mandatory Reading" section before starting

## Process

### Step 1: Load Plan

1. If path provided, read that file
2. If not, search for plan files:
   - `docs/plans/` and `docs/superpowers/plans/`
   - Match against current branch name
   - If multiple found, ask user which one
3. Parse the plan into tasks and steps

### Step 2: Read Mandatory Files

Read every file listed in the plan's "Mandatory Reading" section. This ensures you have the codebase context needed for implementation.

#### Knowledge Base Context (if configured)

Check CLAUDE.md for a `## Knowledge Base` section with a `Path:` value. If configured:

1. Read `<kb-path>/wiki/_index.md` for an overview of available knowledge
2. Extract keywords from the current task description
3. Run: `KB_PATH=<kb-path> node cli/kb-search.js search "<task keywords>"`
4. Read the top 3-5 matching wiki articles in full
5. If working on a specific issue, also search: `KB_PATH=<kb-path> node cli/kb-search.js search "#<issue-number>" --type=feature`

This supplements the plan's mandatory reading with wiki knowledge the plan author may not have included. The search automatically finds relevant concepts, decisions, and feature context.

If no knowledge base configured, skip this step.

### Step 2.5: Design-Artifact Branch (mandatory check)

After loading the plan, read its frontmatter. The plan was tagged by `/plan-feature` Phase 1.5 with one of:

- `branch: production-code` → fall through to Step 3 below.
- `branch: design-artifact` → run **2.5a** then **2.5b**.
- `branch: hybrid` → run **2.5a** then **2.5b**, then **2.5c** to hand off to Step 3 for the code phase.

If frontmatter is missing or malformed, stop and ask the user to re-run `/plan-feature` so the routing decision is recorded. Do NOT silently keyword-classify here — that's `/plan-feature`'s job.

#### Step 2.5a: License acknowledgement (first dispatch per repo)

huashu-design is **non-commercial-by-default**. Personal/research/learning use is free; commercial / client-deliverable / enterprise / paid-service use requires authorization from the author (`huasheng` / `花叔`, see `https://github.com/alchaincyf/huashu-design#license--usage-rights`).

The framework auto-dispatches huashu-design from this step. To make license obligations visible at the point of use:

1. Check for `.design-system/.huashu-license-ack`. If it exists, skip to 2.5b.
2. If absent, print the license summary verbatim:

   ```
   This step will dispatch the huashu-design skill (alchaincyf/huashu-design).

   License — personal use is free; commercial/client/enterprise use requires
   authorization from the author. The full terms are at:
   https://github.com/alchaincyf/huashu-design#license--usage-rights

   To proceed, confirm one of:
     - "personal" — personal/research/learning use; no commercial intent
     - "commercial-acked" — commercial use; you have obtained or will obtain
                            authorization from the author
     - "skip" — abort this run; you will use a different design path
   ```

3. On user response `personal` or `commercial-acked`, write the ack file:

   ```bash
   mkdir -p .design-system
   printf 'mode: %s\nacked_at: %s\nfirst_dispatch_commit: %s\n' \
     "<user-response>" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(git rev-parse HEAD 2>/dev/null || echo 'no-commit')" \
     > .design-system/.huashu-license-ack
   ```
4. On `skip`, abort 2.5 and ask the user how they want to proceed instead. Do not auto-fall-through to Step 3 — they explicitly opted out.
5. Stage the ack file so it gets committed with the design output. Future dispatches in this repo see the file and skip the prompt.

#### Step 2.5b: Pre-flight + dispatch

1. **Skill installation check:** `ls ~/.claude/skills/huashu-design/SKILL.md`. If missing, stop and tell the user to run `npx skills add alchaincyf/huashu-design`.
2. **Version-pin check:** Read `.claude/.versions.json`. If `external_skills.huashu-design.skill_md_sha256` is non-empty, hash the installed `SKILL.md` (`shasum -a 256 ~/.claude/skills/huashu-design/SKILL.md`) and compare. On mismatch, warn the operator that the skill has drifted from the tested version; the brand-spec.md schema may have changed; ask whether to proceed.
3. **Brand-spec check** (driven by the plan's `brand_spec` frontmatter field):
   - `bootstrap` → if `.design-system/brand-spec.md` is missing, dispatch `/brand-extract` as Task 0 with default mode.
   - `use-as-is` → dispatch `/brand-extract --mode=codify-as-is` as Task 0 (writes spec from existing CSS without quality gating, with a warning note in `_extraction-log.md`).
   - `skip` → no spec is written; pass the plan's inline constraints to huashu-design directly.
   - `n/a` → existing `.design-system/brand-spec.md` is already current per the staleness check; reuse it.
4. **Staleness check** (when reusing an existing spec):
   - Read the spec's `Generated:` ISO date.
   - If older than 90 days → warn but don't block.
   - If `git log --since=<spec-date> -- 'tailwind.config.*' 'app/globals.css' 'src/styles/**' 'components/ui/**'` returns commits → warn that brand-relevant files changed since the spec was written; suggest a refresh.
5. **Write the design marker** so `spec-reviewer-enforce.sh` allows file writes during the dispatch:

   ```bash
   .claude/hooks/spec-reviewer-marker.sh write design
   ```
6. **Dispatch huashu-design** as the single implementation task, passing:
   - The prompt from the plan
   - The path to `.design-system/brand-spec.md` (or inline constraints if `brand_spec: skip`)
   - The output directory: `design/<feature-slug>/`
   - A directive to follow huashu-design's Junior Designer Workflow (placeholders + reasoning shown early; three iterations: real content → variations → tweaks)
7. After dispatch returns, hand off to `/validate` Phase 2.5 (5D Visual Critique). Do **not** clear the design marker yet — Step 5 (Completion Report) clears it on full `/execute` success. If the run aborts mid-flight, run `.claude/hooks/spec-reviewer-marker.sh clear` manually before re-running.

#### Step 2.5c: Hybrid handoff (only on `branch: hybrid`)

The artifact is now produced under `design/<feature-slug>/`, and a `bundle.json` exists per huashu-design's handoff format. To proceed to the code phase:

1. **Clear the design marker** explicitly so the implementer→reviewer enforcement re-engages:

   ```bash
   .claude/hooks/spec-reviewer-marker.sh clear
   ```
2. Read the bundle as the spec for the second plan section. If the plan author put both phases in one file, locate the `## Code Tasks` section now. If the plan was split into two files (per `/plan-feature` hybrid output), pause and tell the user to invoke `/execute` on the second plan file once they're ready to ship the code.
3. Fall through to **Step 3** for the code-phase tasks. The marker file is now empty/cleared, so the standard implementer→reviewer pairing applies to every subsequent task.

**Otherwise (`branch: production-code`), proceed to Step 3 below.**

### Step 3: Execute Tasks (implementer → reviewer loop, mandatory)

For each task in the plan, dispatch TWO subagents in sequence:

**3a. Task Implementer**
1. Announce: `Starting Task N: [task name] — [dispatch] role=task-implementer task=N`
2. Write the marker so the enforcement hook can see the dispatch in runtimes without transcript access: run `.claude/hooks/spec-reviewer-marker.sh write implementer`
3. Dispatch via superpowers:subagent-driven-development with role `task-implementer`
4. Implementer reads plan task + mandatory files, writes tests first, implements, verifies
5. On implementer return: capture diff (`git diff`) and task exit status

**3b. Spec Reviewer (MANDATORY — DO NOT SKIP)**
1. Announce: `Task N implementer complete — [dispatch] role=spec-reviewer task=N`
2. Dispatch subagent with role `spec-reviewer`, passing:
   - The plan task spec
   - The implementer's diff
   - `.claude/references/spec-reviewer-protocol.md`
3. Reviewer runs the protocol checklist + adversarial questions:
   - "Is the implementer's approach the simplest viable?"
   - "What could be cut without losing acceptance criteria?"
   - "What edge case is missing?"
   - "Does any choice contradict an existing pattern/reference?"
4. Reviewer returns PASS or REQUEST_CHANGES with specific blockers
5. If REQUEST_CHANGES: return to 3a with reviewer output; do NOT proceed to next task
6. If PASS: mark task checkbox done; write the reviewer marker (`.claude/hooks/spec-reviewer-marker.sh write reviewer`); proceed

**Marker coupling:** The literal dispatch markers in the Announce lines (`[dispatch] role=task-implementer task=N` and `[dispatch] role=spec-reviewer task=N`) are structural tokens. The output-compaction Stop hook preserves any line containing `[dispatch] role=` so user-visible compaction never rewrites them (see `.claude/references/hook-ordering.md`). Note: enforcement itself does NOT scan these announcements — the marker file is the single source of truth (see Step 3.5).

**Enforcement (marker-only):** The PostToolUse hook `.claude/hooks/spec-reviewer-enforce.sh` reads ONLY the marker file at `.claude/.last-impl-task`. There is no transcript-scanning fallback — the hook's behavior is deterministic across runtimes regardless of whether `CLAUDE_TRANSCRIPT_PATH` is set. Outcomes:
- Marker absent / empty → allow (no active pair)
- Marker `implementer:<epoch>` within 600s → BLOCK (exit 2)
- Marker `implementer:<epoch>` older than 600s → allow with stale warning to stderr
- Marker `reviewer:<epoch>` → allow (pair complete)
- Any malformed marker → BLOCK with a fix-up message

### Step 3.5: Marker File Discipline

To make the enforcement hook deterministic, `/execute` maintains a marker file at `.claude/.last-impl-task`.

**Format:** `<state>:<epoch>` where `<state>` is one of `implementer` or `reviewer`, and `<epoch>` is the current Unix epoch in seconds (`date +%s`).

- After dispatching a task-implementer (Step 3a), write `implementer:$(date +%s)` via `.claude/hooks/spec-reviewer-marker.sh write implementer`.
- After a spec-reviewer returns PASS (Step 3b), write `reviewer:$(date +%s)` via `.claude/hooks/spec-reviewer-marker.sh write reviewer`.
- If the marker's state is `implementer` when the hook fires, the hook blocks further tool use.
- **Staleness window: 600 seconds (10 minutes).** If the marker's epoch is older than 600s, the hook treats it as stale and does NOT block (exit 0 with an informational warning). The window is intentionally short — long-running subagents rarely exceed it. If a legitimate run does exceed 10 minutes, clear the marker manually with `.claude/hooks/spec-reviewer-marker.sh clear` and retry.
- The marker file is gitignored; it exists only for the duration of an `/execute` run and is deleted on successful completion (Step 5) via `.claude/hooks/spec-reviewer-marker.sh clear`.

### Step 4: Validation

After all tasks are complete:
1. Run the project's full test suite
2. Run lint/type-check if available
3. Verify the application starts without errors

### Step 5: Completion Report

Before emitting the report, tear down the marker file so it cannot poison a later unrelated session: run `.claude/hooks/spec-reviewer-marker.sh clear` when `/execute` completes successfully (all tasks passed) or when the run is explicitly aborted. The helper is a no-op if the file is absent. (The enforcement hook also treats markers older than 10 minutes as stale, so a missed teardown degrades gracefully — but staleness should be the exception, not the norm.)

```
=== Execution Complete ===

Plan: [plan file path]
Tasks completed: N/N
Tests passing: all / N failures
Lint: pass / N issues
Type check: pass / N errors

Next steps:
- Run /validate for full verification
- Run /ship when ready to commit and create PR
```

## Error Handling

- If a task fails and cannot be fixed in 3 attempts: stop, report the issue, ask the user
- If the plan has a bug (wrong file path, missing step): fix the plan and continue
- If a dependency is missing: install it and continue
- Never skip a failing test — either fix the code or report the issue
