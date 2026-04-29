#!/bin/bash
# Hook: PreToolUse on Edit/Write (implementation files only)
# Purpose: Warns if no plan file exists for the current branch
# Behavior: WARN (does not block)

BRANCH=$(git branch --show-current 2>/dev/null)

if [ -z "$BRANCH" ] || [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ]; then
  exit 0
fi

PLAN_EXISTS=$(find docs/plans docs/superpowers/plans -name "*.md" 2>/dev/null | head -1)

if [ -z "$PLAN_EXISTS" ]; then
  echo "NOTE: No implementation plan found for this branch."
  echo "For L/XL tasks, consider running /plan-feature first."
  echo "For small tasks, this is fine — carry on."
fi

exit 0
