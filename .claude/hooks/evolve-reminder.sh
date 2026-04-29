#!/bin/bash
# Hook: Stop (after PR-related commands)
# Purpose: Reminds to run /evolve after merging
# Behavior: REMIND

echo ""
echo "If you just merged a PR, run /evolve to:"
echo "  - Update CLAUDE.md with learnings from this session"
echo "  - Update architect-agent knowledge base"
echo "  - Improve the system for next time"
echo ""

exit 0
