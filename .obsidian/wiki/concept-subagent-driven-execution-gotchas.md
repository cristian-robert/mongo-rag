---
title: "Subagent-driven execution gotchas"
type: concept
tags: [concept, subagents, workflow, development]
status: compiled
created: 2026-05-02
updated: 2026-05-02
sources:
  - sessions/2026-05-02-blobstore-fly-deploy-learnings.md
related:
  - "[[2026-05-02-blobstore-fly-deploy-learnings]]"
---

# Subagent-driven execution gotchas

## Overview

When the orchestrator dispatches a subagent (via the `Agent` tool) to execute a multi-task plan, four failure modes recur often enough to warrant a stable boilerplate. They are independent of which subagent type is used (`general-purpose`, `superpowers:code-reviewer`, etc.) and surface only when the subagent runs more than ~3 sequential steps that involve shell + git + long-running tests. All four were confirmed across the four review-fix waves of PR #83 (BlobStore + Fly deploy follow-ups).

This article exists so future sessions don't have to re-discover them.

## Content

### 1. `commit-commands:commit` skill bridge does not work inside a subagent

The project's mandatory `/commit` flow (per `CLAUDE.md` "Git Workflow" section) is implemented by the `commit-commands:commit` skill. When a subagent invokes that skill via the `Skill` tool, the bridge dispatches a *sub-conversation* rather than giving the subagent direct control over staging — so the subagent observes "skill launched" but never gets to write the commit. Every subagent in PR #83's Wave A/B/C/D hit this and had to be told mid-flight to fall back to direct git.

**Workaround (always inline this in subagent prompts):**

```bash
git add <specific paths>     # surgical staging — never `git add -A` or `git add .`
git commit -m "$(cat <<'EOF'
<conventional commit subject — feat:/fix:/docs:/refactor:/chore:/test:>

<optional body>

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

The HEREDOC trailer matches the project commit pattern (see `git log` for examples). The `Co-Authored-By` line is what `/commit` would have added had it worked.

### 2. CWD drift across turns

A subagent that `cd`s into a subdirectory for tooling (e.g. `cd apps/api && uv run pytest`) keeps that CWD on every subsequent `Bash` call in the same agent run. The orchestrator and subagent each get a separate persistent shell — but inside one subagent, state persists. The most common collision: the subagent runs pytest from `apps/api`, then tries to `git add docs/foo.md` and gets "file not found" because the relative path resolves to `apps/api/docs/foo.md`.

**Workarounds (in order of preference):**

1. **Use absolute paths for git operations:** `git add /Users/.../mongo-rag/docs/foo.md`
2. **Or use `git -C <repo_root>`:** `git -C /Users/.../mongo-rag add docs/foo.md`
3. **Or instruct the subagent explicitly:** "After any `cd apps/api`, `cd ..` back to the repo root before any git operation."

Option 1 or 2 is more robust because option 3 relies on the subagent remembering the rule across many turns, which it sometimes doesn't.

### 3. Output buffering through `tail` defeats progress monitoring

`cmd 2>&1 | tail -N` only flushes its buffer when `cmd` exits. If the orchestrator runs a long-running test suite in the background and tries to read the output file mid-run, the file stays empty until completion. This isn't a bug — it's how `tail` works on a pipe — but it's easy to forget when the orchestrator is also scheduling wakeups based on the file size.

**Fix:**

```bash
# Wrong — output file stays empty until pytest finishes
uv run pytest ... 2>&1 | tail -15 > /tmp/out.log &

# Right — full output streams as it goes; tail at read time, not write time
uv run pytest ... 2>&1 | tee /tmp/out.log &
# then later:  tail -15 /tmp/out.log
```

If you only need the tail (not progress) and don't intend to monitor mid-run, the original form is fine — just don't schedule wakeups expecting partial output.

### 4. Sequential-touch tasks must be serialized; "parallel-safe" is a property of the *file set*, not the agent count

When a plan declares "tasks 1, 2, 6, 7, 8 are parallelizable; tasks 3, 4, 5, 9 must be sequential", the parallel/sequential boundary is determined by which files each task touches, not by how clever the orchestrator is. PR #83's plan grouped four tasks that all mutated `apps/api/src/worker.py` into a sequential wave (B), and the rest into an order-agnostic wave (A). One subagent per wave, sequential commits within the wave, was the simplest and safest pattern.

**The anti-pattern:** dispatching 5 parallel subagents on the same branch in the same working directory. Even if the file sets don't overlap, every `git add` / `git commit` will race for the index lock, and surgical staging falls apart. If you genuinely want parallelism, use `isolation: "worktree"` and merge after — but for small tasks the overhead exceeds the wall-clock savings.

## Key takeaways

- Always inject the **direct-git commit fallback** with HEREDOC + `Co-Authored-By` trailer when dispatching subagents — `/commit` (`commit-commands:commit`) does not work inside them.
- Always require **`git -C <repo_root>` or absolute paths** for git operations in subagents that also `cd` into subdirectories — CWD persists across turns.
- Use **`tee` instead of `tail`** when backgrounding a command and intending to read progress before completion.
- Pre-classify plan tasks as "parallel-safe" vs "sequential-touch" by **file set**, not by guess — and dispatch **one subagent per wave**, sequential within the wave, on the shared branch. Use `isolation: "worktree"` only when the parallelism payoff is large.
- Specify `model: "opus"` (or whatever the project mandates) explicitly on every `Agent` call — subagents inherit, but inheritance is not documented as stable.

## Examples

### Subagent prompt boilerplate (drop-in template)

```text
You are executing <Wave name> of <plan path>.

## Context
- Repo: <absolute path>
- Branch: <name> (already checked out)
- HEAD: <sha>
- Plan file: <path>
- Issue: #<n>

## Tasks (sequential within this wave)
<list with files touched + commit subjects>

## Execution rules
For EACH commit:
1. Read the actual code first; never blindly mutate based on the finding text.
2. TDD where it makes sense — failing test first, then implementation.
3. Run focused tests + lint after each change.
4. Commit using DIRECT GIT (the commit-commands:commit skill bridge does
   not work in subagent context):

   git add <specific paths>     # never `git add -A`
   git commit -m "$(cat <<'EOF'
   <subject>

   Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
   EOF
   )"

5. After each commit: git log -1 --format="%h %s"

## CWD discipline
If you `cd apps/api` for pytest, `cd ..` back before any git operation —
or use `git -C <repo_root>` for git commands.

## Constraints
- Model: Opus 4.7 only.
- No scope creep — only the changes specified per task.
- Do not commit `.obsidian/_search/*.json` — discard with
  `git checkout -- .obsidian/_search/` before committing if they drift.

## Report format
<expected wave summary template>

If any task blocks, stop and report — do not skip ahead.
```

### Wave dispatch shape that works

```text
Wave A (5 tasks, file-disjoint): one subagent, sequential commits.
Wave B (4 tasks, all touch worker.py): one subagent, sequential commits.
Wave C (Copilot fixes, mixed): one subagent, sequential commits, doc fixes first.
Wave D (residual cosmetic): one subagent, sequential commits.

Orchestrator runs full pytest + lint + adversarial review between waves.
```

That's roughly 13 commits per wave at peak; one subagent per wave kept the main session lean while the subagent owned the drudgery.

## See also

- [[2026-05-02-blobstore-fly-deploy-learnings]] — raw session learnings, including a fifth lesson about pre-existing CI failures on `main` that aren't caused by your branch.
- `superpowers:subagent-driven-development` — the upstream skill this article supplements with project-specific gotchas.
- `superpowers:executing-plans` — orchestration counterpart for plan-driven work.
- `.claude/rules/_global.md` — pointer to this article in the Pipeline Discipline section.
