#!/usr/bin/env bash
# Sync secrets from local .env to both Fly apps.
# Usage: ./scripts/fly-secrets.sh [api|worker|both]

set -euo pipefail

TARGET="${1:-both}"

SECRETS=(
  MONGODB_URI
  DATABASE_URL
  SUPABASE_URL
  SUPABASE_SECRET_KEY
  SUPABASE_S3_ACCESS_KEY
  SUPABASE_S3_SECRET_KEY
  SUPABASE_JWT_SECRET
  SUPABASE_STORAGE_BUCKET
  LLM_API_KEY
  EMBEDDING_API_KEY
  STRIPE_SECRET_KEY
  STRIPE_WEBHOOK_SECRET
  REDIS_URL
  BLOB_STORE
  NEXTAUTH_SECRET
)

if [[ ! -f apps/api/.env ]]; then
  echo "ERROR: apps/api/.env not found" >&2
  exit 1
fi

# Load .env into the shell.
set -a
# shellcheck disable=SC1091
source apps/api/.env
set +a

set_for() {
  local app="$1"
  local args=()
  for k in "${SECRETS[@]}"; do
    if [[ -n "${!k:-}" ]]; then
      args+=("${k}=${!k}")
    fi
  done
  if [[ ${#args[@]} -eq 0 ]]; then
    echo "No secrets to set for ${app}"
    return
  fi
  echo "Setting ${#args[@]} secrets on ${app}..."
  fly secrets set --app "${app}" "${args[@]}"
}

case "${TARGET}" in
  api)    set_for mongorag-api ;;
  worker) set_for mongorag-worker ;;
  both)   set_for mongorag-api && set_for mongorag-worker ;;
  *)      echo "Usage: $0 [api|worker|both]" >&2; exit 1 ;;
esac
