#!/usr/bin/env bash
# .claude/hooks/spec-reviewer-enforce.sh
# PostToolUse hook watching TodoWrite / TaskUpdate completions.
#
# Intent: if a task-implementer dispatch just marked a task completed without
# a paired spec-reviewer dispatch following it, block (or warn) so the
# controller doesn't skip the mandatory review step defined in
# .claude/commands/execute.md Step 3b.
#
# DESIGN — marker-only, deterministic (Finding 3 fix):
#   Earlier versions had three fallback tiers (transcript scan → marker file →
#   informational warning). That was non-deterministic: the same violation
#   could block on one tool call and pass on the next depending on whether
#   CLAUDE_TRANSCRIPT_PATH happened to be set. The transcript branch is gone.
#   This hook now relies on a single source of truth: the marker file written
#   by spec-reviewer-marker.sh.
#
# Marker file contract (.claude/.last-impl-task):
#   Marker absent OR file empty                         → exit 0 (no active pair)
#   "implementer:<epoch>" within STALE_SECS             → exit 2 (block, pair missing)
#   "implementer:<epoch>" older than STALE_SECS         → exit 0 (stale; warn to stderr)
#   "reviewer:<epoch>"                                  → exit 0 (pair complete)
#   "design:<epoch>"                                    → exit 0 (design-artifact path
#                                                                bypasses pairing — see
#                                                                /execute Step 2.5)
#   any other content (malformed)                       → exit 2 (block, force fix-up)
#
# STALE_SECS reduced from 3600s (1h) to 600s (10min) — long-running subagents
# rarely exceed this. If they do, the operator should clear the marker
# manually with `.claude/hooks/spec-reviewer-marker.sh clear`. Documented in
# .claude/commands/execute.md Step 3.5.
#
# Robustness:
#   - Handles empty stdin (used by smoke tests) without crashing.
#   - Never reads CLAUDE_TRANSCRIPT_PATH; transcript fallback was removed.
#   - Never crashes the harness on missing tools.
set -uo pipefail

PROTOCOL_REF=".claude/references/spec-reviewer-protocol.md"
MARKER_FILE=".claude/.last-impl-task"
STALE_SECS=600

# Read stdin defensively. `read` would block; `cat` with a guard does not.
input=""
if [ ! -t 0 ]; then
  input="$(cat || true)"
fi

# If stdin is empty (smoke test / no payload), exit cleanly without output.
if [ -z "${input// /}" ]; then
  exit 0
fi

# Marker absent → no active implementer/reviewer pair → exit 0.
if [ ! -e "$MARKER_FILE" ]; then
  exit 0
fi

# Read marker (best-effort). Truly empty marker file → treat as absent.
marker_raw="$(cat "$MARKER_FILE" 2>/dev/null || true)"
if [ -z "${marker_raw// /}" ]; then
  exit 0
fi

# Parse "<state>:<epoch>". A malformed marker (no colon, or unknown state)
# is a contract violation — block and tell the operator to fix it.
if [[ "$marker_raw" != *:* ]]; then
  echo "BLOCK: $MARKER_FILE is malformed: '$marker_raw'" >&2
  echo "Expected format: <implementer|reviewer|design>:<epoch>. Run \`.claude/hooks/spec-reviewer-marker.sh clear\` and retry." >&2
  exit 2
fi

marker_state="${marker_raw%%:*}"
marker_epoch="${marker_raw#*:}"

# Validate epoch is a non-negative integer; otherwise the marker is corrupt.
if ! [[ "$marker_epoch" =~ ^[0-9]+$ ]]; then
  echo "BLOCK: $MARKER_FILE has invalid epoch: '$marker_epoch'" >&2
  echo "Run \`.claude/hooks/spec-reviewer-marker.sh clear\` and retry." >&2
  exit 2
fi

case "$marker_state" in
  implementer)
    now="$(date +%s 2>/dev/null || echo 0)"
    if [ "$now" -gt 0 ] && [ "$marker_epoch" -gt 0 ]; then
      age=$(( now - marker_epoch ))
      if [ "$age" -gt "$STALE_SECS" ]; then
        echo "NOTE: $MARKER_FILE is stale (age ${age}s > ${STALE_SECS}s); not blocking." >&2
        echo "      Clear it manually if the prior /execute run was abandoned: .claude/hooks/spec-reviewer-marker.sh clear" >&2
        exit 0
      fi
    fi
    echo "BLOCK: implementer task completed without spec-reviewer dispatch." >&2
    echo "See $PROTOCOL_REF — every implementer MUST be paired with a spec-reviewer." >&2
    exit 2
    ;;
  reviewer)
    exit 0
    ;;
  design)
    # Design-artifact path (huashu-design / brand-extract) bypasses the
    # implementer→reviewer pairing — design tasks have a different validation
    # path (/validate Phase 2.5: 5D Visual Critique). The marker still records
    # the dispatch so that on a hybrid plan, when /execute later flips to a
    # code task, the operator must explicitly clear or rewrite the marker
    # before the implementer→reviewer enforcement re-engages.
    exit 0
    ;;
  *)
    echo "BLOCK: $MARKER_FILE has unknown state: '$marker_state'" >&2
    echo "Expected 'implementer', 'reviewer', or 'design'. Run \`.claude/hooks/spec-reviewer-marker.sh clear\` and retry." >&2
    exit 2
    ;;
esac
