#!/bin/bash
# Hook: PreToolUse on Bash
# Purpose: Prevents direct commits and pushes to main/master
# Behavior: BLOCK

COMMAND="$*"

if echo "$COMMAND" | grep -qE 'git (commit|push).*(main|master)'; then
  echo "BLOCKED: Direct commits/pushes to main/master are not allowed."
  echo "Create a feature branch first: git checkout -b feat/your-feature"
  echo "Then use /ship to commit, push, and create a PR."
  exit 1
fi

exit 0
