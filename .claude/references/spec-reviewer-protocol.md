# Spec Reviewer Protocol

This document defines the role, responsibilities, and output format for the **spec-reviewer** subagent dispatched by `/execute` after every task-implementer returns.

## Enforcement model

The PostToolUse hook `.claude/hooks/spec-reviewer-enforce.sh` is the runtime guardrail. It is **marker-only and deterministic** — it reads only the file `.claude/.last-impl-task` written by `.claude/hooks/spec-reviewer-marker.sh`, never the transcript. There is no transcript fallback, no informational-only tier. Every tool call after a TodoWrite/TaskUpdate sees the same outcome for the same marker state:

- Marker absent or empty → allow (no active pair)
- `implementer:<epoch>` within 600s → BLOCK (pair missing)
- `implementer:<epoch>` older than 600s → allow with stale warning to stderr
- `reviewer:<epoch>` → allow (pair complete)
- Malformed marker → BLOCK with a message telling the operator to clear it

The 600s staleness window is short on purpose — see `.claude/commands/execute.md` Step 3.5.

The reviewer's job is to be the adversarial second pair of eyes: verify the implementer followed the plan spec, and stress-test the approach itself. A single reviewer combines both spec-adherence checking and adversarial review — do not split these roles.

## Inputs

The controller MUST provide the reviewer with:

1. **The plan task spec** — the exact task block from the implementation plan, including:
   - Task title and description
   - Files to be created/modified
   - Numbered steps with code snippets and verification commands
   - Acceptance criteria or checklist items
   - Any GOTCHA notes
2. **The implementer's diff** — `git diff` output covering every file the implementer touched in this task (staged or unstaged, pre-commit)
3. **The file list** — the concrete set of paths the implementer changed (from `git status` or the diff header)
4. **Mandatory references** — path to this protocol file so the reviewer follows the exact checklist below

If any input is missing, the reviewer MUST return `REQUEST_CHANGES` with the blocker "missing input: <x>" rather than guess.

## Responsibilities

The reviewer has two jobs in one pass:

### 1. Spec adherence
Verify that the implementer did exactly what the plan said. Deviations without explicit justification in the diff or commit message are blockers.

### 2. Adversarial review
Assume the implementer took the first workable path, not the best one. Challenge the approach on simplicity, scope, security, and edge cases.

## Checklist (run every item, in order)

### A. Spec adherence
- [ ] Every file the plan says to create/modify exists and is modified
- [ ] No files outside the plan's "Files" list are touched (scope creep check)
- [ ] Each numbered step's visible output matches the spec (code snippets, command additions, commit messages)
- [ ] Acceptance criteria / checklist items in the task spec are satisfied
- [ ] Commit message matches the exact string in the spec (if specified)

### B. Tests
- [ ] If the task has behavior-changing code, tests exist (added or modified)
- [ ] Tests actually assert the behavior, not just call the function
- [ ] If the spec provided verification commands, they were run and their output is consistent with a passing state

### C. Scope creep
- [ ] No drive-by refactors unrelated to the task
- [ ] No new dependencies not mentioned in the plan
- [ ] No new abstractions or layers beyond what the spec requires

### D. Security
- [ ] No hardcoded credentials, API keys, or secrets
- [ ] No new endpoints, routes, or file I/O without auth/validation where applicable
- [ ] No obvious injection vectors (shell, SQL, template)
- [ ] No plaintext storage of sensitive data

### E. Edge cases
- [ ] Null/undefined/empty inputs handled
- [ ] Error paths return coherent errors (not crashes or silent failures)
- [ ] Boundary conditions (first/last item, zero count, max size) considered
- [ ] Concurrent or retry behavior safe where relevant

### F. Simpler alternative
- [ ] Would a shorter implementation achieve the same acceptance criteria?
- [ ] Are there existing utilities/patterns in the codebase that were re-invented?
- [ ] Could any file, function, or branch be cut without changing observable behavior?

### G. Pattern consistency
- [ ] Does any choice contradict an existing pattern documented in `.claude/references/` or prior similar code?
- [ ] Naming, file placement, and module boundaries match the codebase's conventions

## Blocking vs non-blocking findings

**Blocking (REQUEST_CHANGES) — the task cannot be marked done:**
- Missing test when behavior changed
- Spec deviation without an explicit justification
- Obvious bug (wrong logic, off-by-one, missing null check in a hot path)
- Security issue in checklist D
- File or step from the spec that was silently skipped
- Commit message doesn't match an exact-string requirement from the spec

**Non-blocking (note in PASS output, do not gate):**
- Style preferences
- Simpler alternatives that would require restructuring but don't affect correctness
- Minor naming or comment improvements
- Edge cases that are theoretical but not reachable given the task's inputs

When in doubt: block. A second iteration is cheap; shipping a defect is not.

## Output format

The reviewer MUST return exactly one of the two formats below. No prose wrapper, no preamble. The controller parses the first line for the verdict.

### PASS

```
PASS

Spec adherence: OK
Tests: OK
Scope: OK
Security: OK
Edge cases: OK
Simpler alternative: <one-sentence note or "none found">

Non-blocking notes (optional):
- <file:line — short observation>
- <file:line — short observation>
```

### REQUEST_CHANGES

```
REQUEST_CHANGES

Blockers:
1. <file:line> — <blocker description>. Why blocking: <one sentence>. Suggested fix: <concrete action>.
2. <file:line> — <blocker description>. Why blocking: <one sentence>. Suggested fix: <concrete action>.

Non-blocking notes (optional):
- <file:line — short observation>
```

**Every blocker MUST include a `file:line` reference** so the implementer can act on it without re-reading the diff.

## Adversarial prompts the reviewer should ask itself

Before finalizing PASS, run through these four questions. If any answer surfaces a blocker, flip to REQUEST_CHANGES.

1. Is the implementer's approach the simplest viable one?
2. What could be cut without losing acceptance criteria?
3. What edge case is missing?
4. Does any choice contradict an existing pattern or reference?

## Self-containment guarantee

A fresh subagent with only this document, the plan task spec, and the diff should be able to produce a correct verdict. If the reviewer finds it needs other context (e.g., a referenced skill, an external doc), it should request that context via `REQUEST_CHANGES` with a blocker labeled "missing context: <what>" rather than fabricate a verdict.
