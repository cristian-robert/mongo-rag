#!/usr/bin/env bash
# Postgres (Supabase) backup script using pg_dump in custom format.
#
# Usage:
#   DATABASE_URL="postgresql://..." \
#   BACKUP_DIR="./.backups/postgres" \
#   [S3_BUCKET="s3://my-bucket/mongo-rag/postgres"] \
#   [S3_ENDPOINT_URL="https://..."] \
#   [RETENTION_DAYS=30] \
#   ./scripts/backup/postgres_backup.sh [--dry-run]
#
# Notes:
#   - Uses pg_dump --format=custom (.dump) which is restorable with pg_restore.
#   - Supabase also runs its own managed daily backups; this script is for
#     additional self-controlled backups (long retention, off-platform).
set -euo pipefail

DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help)
      sed -n '2,16p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 64
      ;;
  esac
done

: "${DATABASE_URL:?DATABASE_URL must be set}"
BACKUP_DIR="${BACKUP_DIR:-./.backups/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ARCHIVE="${BACKUP_DIR}/postgres-${TIMESTAMP}.dump"

mkdir -p "$BACKUP_DIR"

echo "[pg-backup] target=${ARCHIVE} retention_days=${RETENTION_DAYS} dry_run=${DRY_RUN}"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[pg-backup] dry-run: would invoke pg_dump --format=custom"
  if [[ -n "${S3_BUCKET:-}" ]]; then
    echo "[pg-backup] dry-run: would upload to ${S3_BUCKET}/$(basename "$ARCHIVE")"
  fi
  echo "[pg-backup] dry-run: would prune files older than ${RETENTION_DAYS}d in ${BACKUP_DIR}"
  exit 0
fi

if ! command -v pg_dump >/dev/null 2>&1; then
  echo "pg_dump is not installed (install postgresql-client)" >&2
  exit 127
fi

# pg_dump reads URL from positional arg; we never echo it.
pg_dump --format=custom --no-owner --no-acl --quote-all-identifiers \
  --file="$ARCHIVE" "$DATABASE_URL"

if [[ ! -s "$ARCHIVE" ]]; then
  echo "[pg-backup] dump is empty or missing: $ARCHIVE" >&2
  exit 1
fi

echo "[pg-backup] wrote $(du -h "$ARCHIVE" | cut -f1) to ${ARCHIVE}"

if [[ -n "${S3_BUCKET:-}" ]]; then
  if ! command -v aws >/dev/null 2>&1; then
    echo "[pg-backup] aws CLI not installed; skipping upload" >&2
  else
    AWS_ARGS=()
    if [[ -n "${S3_ENDPOINT_URL:-}" ]]; then
      AWS_ARGS+=("--endpoint-url" "$S3_ENDPOINT_URL")
    fi
    aws "${AWS_ARGS[@]}" s3 cp \
      --only-show-errors \
      --sse AES256 \
      "$ARCHIVE" "${S3_BUCKET%/}/$(basename "$ARCHIVE")"
    echo "[pg-backup] uploaded to ${S3_BUCKET%/}/$(basename "$ARCHIVE")"
  fi
fi

# Local retention; off-platform copies are the authoritative long-term store.
find "$BACKUP_DIR" -type f -name 'postgres-*.dump' -mtime "+${RETENTION_DAYS}" -print -delete \
  || true
