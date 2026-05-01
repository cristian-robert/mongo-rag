---
title: "Subagent-driven execution gotchas"
type: concept
tags: [concept, subagents, workflow, development]
status: stub
created: 2026-05-02
updated: 2026-05-02
related:
  - "[[2026-05-02-blobstore-fly-deploy-learnings]]"
---

# Subagent-driven execution gotchas

Three recurring failure modes when dispatching subagents to execute multi-task plans. All confirmed across 4+ subagent dispatches in PR #83.

## 1. `commit-commands:commit` skill bridge fails in subagents

The skill bridge dispatches a sub-conversation instead of giving the subagent direct control over staging. Subagents must fall back to direct git:

```
git add <specific paths>
git commit -m "$(cat <<'EOF'
<subject>

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Always include this fallback instruction in the subagent prompt explicitly. Never `git add -A` / `git add .` in subagents — surgical staging only.

## 2. CWD drift across turns

A subagent that `cd`s into a subdirectory for tooling (e.g., `cd apps/api` for `uv run pytest`) keeps that CWD on subsequent tool calls within the same agent run. Always include the rule "after `cd apps/api`, `cd ..` back before any git operation" in the prompt, or use absolute paths.

## 3. Output buffering through `tail`

Bash `cmd 2>&1 | tail -N` flushes only when `cmd` exits. If you background a long-running command for monitoring, the output file stays empty until completion. Use `tee output.log` and `tail -f output.log` instead, or drop `tail` and stream the full output.

## See also

- Raw session: [[2026-05-02-blobstore-fly-deploy-learnings]] — full context and a fourth learning on dual-layer code review

## TODO (for `/kb compile`)

- Cross-link to existing skill: `superpowers:subagent-driven-development`, `superpowers:executing-plans`
- Add a "subagent prompt template" section with the 3 boilerplate guards
