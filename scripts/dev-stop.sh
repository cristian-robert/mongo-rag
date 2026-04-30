#!/usr/bin/env bash
# Stop the hybrid dev stack started by scripts/dev.sh.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION="mongorag"

tmux kill-session -t "$SESSION" 2>/dev/null && echo "→ killed tmux session: $SESSION" || true

docker compose -f "$ROOT/docker-compose.dev.yml" down
echo "→ stopped redis + worker"
