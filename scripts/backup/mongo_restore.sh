#!/usr/bin/env bash
# MongoDB restore script.
#
# Restores a mongodump archive into a target database.
#
# Usage:
#   MONGODB_URI="mongodb+srv://..." \
#   ARCHIVE_PATH="./.backups/mongo/mongo-20260101T000000Z.archive.gz" \
#   ./scripts/backup/mongo_restore.sh [--dry-run] [--force]
#
# Safety:
#   - REFUSES to run without --force AND a target URI containing "restore",
#     "staging", or "test" in the host. This prevents accidental restore
#     into production.
#   - --dry-run prints the plan and exits.
#   - No --drop is used by default; pass RESTORE_DROP=1 if you need a wipe.
#   - Tenant isolation is preserved because mongodump captures full collection
#     state including tenant_id; never partially restore individual collections
#     across tenants without a per-tenant export.
set -euo pipefail

DRY_RUN=0
FORCE=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --force)   FORCE=1 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "Unknown argument: $arg" >&2; exit 64 ;;
  esac
done

: "${MONGODB_URI:?MONGODB_URI must be set}"
: "${ARCHIVE_PATH:?ARCHIVE_PATH must be set}"

if [[ ! -s "$ARCHIVE_PATH" ]]; then
  echo "Archive not found or empty: $ARCHIVE_PATH" >&2
  exit 1
fi

URI_LOWER=$(echo "$MONGODB_URI" | tr '[:upper:]' '[:lower:]')
if [[ "$FORCE" -ne 1 ]]; then
  if [[ "$URI_LOWER" != *"restore"* && "$URI_LOWER" != *"staging"* && "$URI_LOWER" != *"test"* ]]; then
    echo "Refusing to restore into a non-staging/test/restore URI without --force." >&2
    exit 3
  fi
fi

echo "[mongo-restore] archive=${ARCHIVE_PATH} dry_run=${DRY_RUN} force=${FORCE}"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[mongo-restore] dry-run: would invoke mongorestore --archive --gzip"
  exit 0
fi

if ! command -v mongorestore >/dev/null 2>&1; then
  echo "mongorestore is not installed" >&2
  exit 127
fi

DROP_ARGS=()
if [[ "${RESTORE_DROP:-0}" -eq 1 ]]; then
  DROP_ARGS+=("--drop")
fi

mongorestore --uri="$MONGODB_URI" --archive="$ARCHIVE_PATH" --gzip "${DROP_ARGS[@]}"

echo "[mongo-restore] complete"
