#!/usr/bin/env bash
# Hybrid local dev launcher.
#   - redis + celery worker:  docker
#   - api (FastAPI)        :  host  (uvicorn --reload)
#   - web (Next.js)        :  host  (pnpm dev)
# All three run in a single tmux session with split panes.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION="mongorag"
COMPOSE_FILE="$ROOT/docker-compose.dev.yml"

# --- BlobStore wiring ---
# Default to filesystem mode for local dev. The host API and the dockerized
# worker share $ROOT/.tmp/uploads (host) ↔ /workspace/.tmp/uploads (container)
# via the bind-mount declared in docker-compose.dev.yml.
export BLOB_STORE="${BLOB_STORE:-fs}"
export UPLOAD_TEMP_DIR="${UPLOAD_TEMP_DIR:-$ROOT/.tmp/uploads}"
mkdir -p "$UPLOAD_TEMP_DIR"

echo "BLOB_STORE=${BLOB_STORE}"

# Fail fast: supabase mode requires creds. Without this, the API silently
# falls through to a code path that errors at request time.
if [[ "${BLOB_STORE}" == "supabase" ]]; then
  : "${SUPABASE_STORAGE_BUCKET:?SUPABASE_STORAGE_BUCKET required when BLOB_STORE=supabase}"
  : "${SUPABASE_SECRET_KEY:?SUPABASE_SECRET_KEY required when BLOB_STORE=supabase}"
  : "${SUPABASE_URL:?SUPABASE_URL required when BLOB_STORE=supabase}"
fi

# Pre-flight: required tools.
for bin in tmux docker uv pnpm; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "missing: $bin — install it before running this script" >&2
    exit 1
  fi
done

# Bring up docker bits (build worker image on first run).
echo "→ starting redis + worker (docker)"
docker compose -f "$COMPOSE_FILE" up -d --build

# Wait for redis healthcheck so api/worker can connect immediately.
echo "→ waiting for redis healthcheck"
until [ "$(docker inspect -f '{{.State.Health.Status}}' "$(docker compose -f "$COMPOSE_FILE" ps -q redis)" 2>/dev/null)" = "healthy" ]; do
  sleep 1
done

# Tear down any stale tmux session before recreating.
tmux kill-session -t "$SESSION" 2>/dev/null || true

echo "→ launching tmux session: $SESSION"

# Pane 0 (top-left): api (FastAPI). Override REDIS_URL because api runs
# on the host but redis is reachable as localhost:6379.
tmux new-session -d -s "$SESSION" -n dev -c "$ROOT/apps/api"
tmux send-keys -t "$SESSION:dev.0" \
  "REDIS_URL=redis://localhost:6379/0 uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8100" C-m

# Pane 1 (top-right): web (Next.js dev server).
tmux split-window -h -t "$SESSION:dev" -c "$ROOT/apps/web"
tmux send-keys -t "$SESSION:dev.1" "pnpm dev" C-m

# Pane 2 (bottom): docker logs (redis + worker).
tmux select-pane -t "$SESSION:dev.0"
tmux split-window -v -t "$SESSION:dev.0" -c "$ROOT"
tmux send-keys -t "$SESSION:dev.2" \
  "docker compose -f docker-compose.dev.yml logs -f" C-m

tmux select-layout -t "$SESSION:dev" tiled
tmux select-pane -t "$SESSION:dev.0"

cat <<EOF
attached. tmux cheat-sheet:
  Ctrl-b o        cycle panes
  Ctrl-b arrow    move between panes
  Ctrl-b z        zoom (fullscreen) current pane, again to unzoom
  Ctrl-b d        detach (leave running)
  scripts/dev-stop.sh   stop everything
EOF

tmux attach -t "$SESSION"
