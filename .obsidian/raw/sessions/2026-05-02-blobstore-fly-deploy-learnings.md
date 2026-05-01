---
title: "Session learnings — #79 BlobStore + Fly deploy"
date: 2026-05-02
tags: [session-learning, subagents, code-review, workflow]
status: pending
related:
  - "[[concept-subagent-driven-execution-gotchas]]"
---

# Session — #79 BlobStore + Fly deploy

Closed PR #83 (44 commits, merge `b39e657`) across 5 review waves: original adversarial review (2 Crit + 4 High), reviewer follow-ups Wave A/B (5 Med + 4 Low), Copilot review Wave C (7 findings), residual parity Wave D (4 findings). 22 findings total, 0 left open. 30+ new tests added.

---

## Durable learnings (worth carrying forward)

### 1. Subagent gotcha — `commit-commands:commit` skill bridge does not work in subagent context

Hit on every subagent dispatch (4 waves). When a subagent invokes the `commit-commands:commit` skill via the `Skill` tool, the bridge dispatches a *sub-conversation* rather than letting the subagent drive the staging step itself, so it can't actually create the commit.

**Workaround:** subagents must fall back to direct git:

```bash
git add <specific paths>     # never `git add -A` or `git add .`
git commit -m "$(cat <<'EOF'
<conventional commit subject>

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Always include this fallback instruction explicitly in the subagent prompt — the subagent doesn't know `commit-commands:commit` is broken for it. Tell it to use direct git with HEREDOC + the `Co-Authored-By` trailer.

### 2. Subagent gotcha — CWD drifts across turns

Subagents that `cd apps/api` for `uv run pytest` keep that CWD on subsequent turns. Multiple commits got blocked on bad paths until I reset CWD in the resume prompt.

**Workaround:** include in every subagent prompt: "If you `cd apps/api` for pytest, `cd ..` back before commits so the repo-root context is correct." Or use absolute paths / `git -C <repo_root>`.

### 3. Bash background gotcha — `cmd | tail -N` defers all output to process end

I scheduled wakeups to read pytest output and the file stayed empty for ~12 minutes. Cause: `uv run pytest -m "not integration" -q 2>&1 | tail -15` — `tail`'s output buffer flushes only when the pipe closes (i.e., pytest exits). Not a bug; just a thing to predict next time.

**Workaround:** for monitorable progress, drop `tail` and use `tee` to a file, then `tail -f` the file. Or grep on partial output as it streams.

### 4. Dual-layer review catches different bug classes

Two review agents in sequence caught complementary failures on the same branch:

- **`superpowers:code-reviewer` (adversarial pass against the plan):** found design / spec-adherence gaps and parity issues (`file://` percent-decode missing, `load_settings()` double-call, comment hygiene, observability mis-classification). Strong on "did the fix match the intent of the original finding."
- **PR-time Copilot review (post-push):** found *real correctness bugs the adversarial reviewer missed entirely* — most importantly an unbounded streaming upload (DoS / cost vector) and a state-machine bug where retryable exceptions flipped the doc to FAILED *before* Celery autoretries. Strong on cross-file flow analysis ("the size cap is checked here but not enforced when streamed there").

**Lesson:** they are not redundant. Run the adversarial reviewer pre-push to confirm closure of known findings; let Copilot run post-push to catch what hasn't been put on anyone's list yet. Default workflow: `superpowers:code-reviewer` → push → wait for Copilot → triage Copilot findings as a fresh wave.

### 5. Project quirk — main has been red on CI for days; do not assume CI failures on a feature branch are caused by that branch

Hit at merge time. PR #83 had 3 failing CI checks (lint, type-check, unit tests) and main itself had been failing the same checks for ~3 days. Spent 5 minutes confirming the failures were inherited, not introduced. **Always check main's CI history before diagnosing PR CI failures.**

`gh run list --branch main --workflow CI --limit 5` is the one-shot. The user merged with the inherited failures; a separate hygiene PR is the right way to clean those.

---

## Non-durable / session-specific (not worth elevating)

- BlobStore architecture details — already captured in `decision-blobstore-handoff.md`, `decision-deploy-fly-vercel.md`, `concept-celery-ingestion-worker.md`, `feature-document-ingestion.md`. No update needed.
- Storage S3 keys ≠ service-role key gotcha — already in `docs/deploy.md` + `apps/api/.env.example` callouts.
- `_will_celery_retry(task, exc)` predicate, `_emit_ingestion_complete` unified helper — useful project patterns but discoverable from worker.py source. Not worth a wiki entry unless they get reused elsewhere.

---

## Plan files written this session

- `docs/superpowers/plans/2026-05-01-blobstore-fly-deploy-followups.md` — already on main
- (No new specs)

## Architect-agent RECORD calls

None. Structural changes were already RECORD'd in commit `9aba554` (deploy guide + wiki articles + architect-agent RECORD) before this session began. Wave A/B/C/D were all hardening of existing modules — no new domains or collections.
