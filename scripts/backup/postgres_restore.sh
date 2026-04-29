#!/usr/bin/env bash
# Postgres restore script.
#
# Usage:
#   DATABASE_URL="postgresql://..." \
#   ARCHIVE_PATH="./.backups/postgres/postgres-20260101T000000Z.dump" \
#   ./scripts/backup/postgres_restore.sh [--dry-run] [--force]
#
# Safety:
#   - REFUSES without --force AND a host name containing restore/staging/test.
#   - Uses pg_restore --clean --if-exists; no DROP DATABASE.
set -euo pipefail

DRY_RUN=0
FORCE=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --force)   FORCE=1 ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "Unknown argument: $arg" >&2; exit 64 ;;
  esac
done

: "${DATABASE_URL:?DATABASE_URL must be set}"
: "${ARCHIVE_PATH:?ARCHIVE_PATH must be set}"

if [[ ! -s "$ARCHIVE_PATH" ]]; then
  echo "Archive not found or empty: $ARCHIVE_PATH" >&2
  exit 1
fi

URL_LOWER=$(echo "$DATABASE_URL" | tr '[:upper:]' '[:lower:]')
if [[ "$FORCE" -ne 1 ]]; then
  if [[ "$URL_LOWER" != *"restore"* && "$URL_LOWER" != *"staging"* && "$URL_LOWER" != *"test"* ]]; then
    echo "Refusing to restore into a non-staging/test/restore URL without --force." >&2
    exit 3
  fi
fi

echo "[pg-restore] archive=${ARCHIVE_PATH} dry_run=${DRY_RUN} force=${FORCE}"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[pg-restore] dry-run: would invoke pg_restore --clean --if-exists"
  exit 0
fi

if ! command -v pg_restore >/dev/null 2>&1; then
  echo "pg_restore is not installed" >&2
  exit 127
fi

pg_restore --clean --if-exists --no-owner --no-acl \
  --dbname="$DATABASE_URL" "$ARCHIVE_PATH"

echo "[pg-restore] complete"
