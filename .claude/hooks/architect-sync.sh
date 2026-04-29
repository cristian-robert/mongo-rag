#!/bin/bash
# Hook: PostToolUse on Write/Edit
# Purpose: Reminds to update architect-agent after structural changes
# Behavior: REMIND

FILE="$1"

if echo "$FILE" | grep -qE '\.(module|controller|service|guard|middleware|resolver)\.(ts|js)$'; then
  echo "REMINDER: Structural file changed. After completing this feature,"
  echo "run architect-agent RECORD to update the codebase knowledge base."
fi

if echo "$FILE" | grep -qE '(migration|schema|\.sql)'; then
  echo "REMINDER: Database schema changed. Run architect-agent RECORD"
  echo "and check Supabase advisors (get_advisors) for security/performance."
fi

exit 0
