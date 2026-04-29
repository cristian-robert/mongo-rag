#!/usr/bin/env bash
# .claude/hooks/spec-reviewer-marker.sh
#
# Marker-file lifecycle helper for the /execute implementer→reviewer pairing.
# Writes or clears .claude/.last-impl-task so spec-reviewer-enforce.sh can
# enforce the pairing in runtimes without CLAUDE_TRANSCRIPT_PATH access.
#
# Usage:
#   .claude/hooks/spec-reviewer-marker.sh write implementer
#   .claude/hooks/spec-reviewer-marker.sh write reviewer
#   .claude/hooks/spec-reviewer-marker.sh write design
#   .claude/hooks/spec-reviewer-marker.sh clear
#
# Marker format: "<state>:<epoch>" where state ∈ {implementer, reviewer, design} and
# epoch is `date +%s` at write time. Matches the format documented in
# .claude/commands/execute.md Step 3.5 and consumed by spec-reviewer-enforce.sh.
#
# Exit codes:
#   0  on success or harmless no-op (clear when file absent)
#   2  on invalid arguments

set -uo pipefail

MARKER_FILE=".claude/.last-impl-task"

usage() {
  cat >&2 <<'EOF'
Usage: spec-reviewer-marker.sh <write implementer|write reviewer|write design|clear>

  write implementer  — record an implementer dispatch (code task)
  write reviewer     — record a spec-reviewer PASS (code task)
  write design       — record a design-artifact dispatch (huashu-design or
                       brand-extract path; bypasses implementer→reviewer pairing)
  clear              — remove the marker (end of /execute)
EOF
}

action="${1:-}"
arg="${2:-}"

case "$action" in
  write)
    case "$arg" in
      implementer|reviewer|design)
        mkdir -p "$(dirname "$MARKER_FILE")"
        epoch="$(date +%s 2>/dev/null || echo 0)"
        printf '%s:%s' "$arg" "$epoch" > "$MARKER_FILE"
        exit 0
        ;;
      *)
        echo "error: write requires 'implementer', 'reviewer', or 'design'" >&2
        usage
        exit 2
        ;;
    esac
    ;;
  clear)
    if [ -e "$MARKER_FILE" ]; then
      rm -f "$MARKER_FILE"
    fi
    exit 0
    ;;
  ""|-h|--help)
    usage
    [ -z "$action" ] && exit 2 || exit 0
    ;;
  *)
    echo "error: unknown action '$action'" >&2
    usage
    exit 2
    ;;
esac
