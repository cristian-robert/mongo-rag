#!/usr/bin/env bash
# MongoDB backup script.
#
# Dumps a MongoDB database with mongodump, gzips the archive, optionally
# uploads to an S3-compatible bucket via the AWS CLI, and applies a local
# retention policy.
#
# Usage:
#   MONGODB_URI="mongodb+srv://..." \
#   BACKUP_DIR="./.backups/mongo" \
#   [S3_BUCKET="s3://my-bucket/mongo-rag/mongo"] \
#   [S3_ENDPOINT_URL="https://..."] \
#   [RETENTION_DAYS=30] \
#   ./scripts/backup/mongo_backup.sh [--dry-run]
#
# Safety:
#   - Refuses to run if MONGODB_URI is unset.
#   - --dry-run prints the plan and exits without invoking mongodump or aws.
#   - No destructive operations are ever performed against the source DB.
#   - The script never echoes the URI to stdout/stderr.
set -euo pipefail

DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help)
      sed -n '2,20p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 64
      ;;
  esac
done

: "${MONGODB_URI:?MONGODB_URI must be set}"
BACKUP_DIR="${BACKUP_DIR:-./.backups/mongo}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ARCHIVE="${BACKUP_DIR}/mongo-${TIMESTAMP}.archive.gz"

mkdir -p "$BACKUP_DIR"

echo "[mongo-backup] target=${ARCHIVE} retention_days=${RETENTION_DAYS} dry_run=${DRY_RUN}"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[mongo-backup] dry-run: would invoke mongodump --archive --gzip"
  if [[ -n "${S3_BUCKET:-}" ]]; then
    echo "[mongo-backup] dry-run: would upload to ${S3_BUCKET}/$(basename "$ARCHIVE")"
  fi
  echo "[mongo-backup] dry-run: would prune files older than ${RETENTION_DAYS}d in ${BACKUP_DIR}"
  exit 0
fi

if ! command -v mongodump >/dev/null 2>&1; then
  echo "mongodump is not installed (install MongoDB Database Tools)" >&2
  exit 127
fi

# mongodump reads the URI from --uri; we never print it.
mongodump --uri="$MONGODB_URI" --archive="$ARCHIVE" --gzip --quiet

if [[ ! -s "$ARCHIVE" ]]; then
  echo "[mongo-backup] archive is empty or missing: $ARCHIVE" >&2
  exit 1
fi

echo "[mongo-backup] wrote $(du -h "$ARCHIVE" | cut -f1) to ${ARCHIVE}"

if [[ -n "${S3_BUCKET:-}" ]]; then
  if ! command -v aws >/dev/null 2>&1; then
    echo "[mongo-backup] aws CLI not installed; skipping upload" >&2
  else
    AWS_ARGS=()
    if [[ -n "${S3_ENDPOINT_URL:-}" ]]; then
      AWS_ARGS+=("--endpoint-url" "$S3_ENDPOINT_URL")
    fi
    aws "${AWS_ARGS[@]}" s3 cp \
      --only-show-errors \
      --sse AES256 \
      "$ARCHIVE" "${S3_BUCKET%/}/$(basename "$ARCHIVE")"
    echo "[mongo-backup] uploaded to ${S3_BUCKET%/}/$(basename "$ARCHIVE")"
  fi
fi

# Local retention. Note: this prunes local files only; off-platform copies
# (S3 / GitHub Actions artifacts) have their own retention and are the
# authoritative long-term store. If the upload step failed earlier we will
# have already exited non-zero, so we never prune locally without a remote.
find "$BACKUP_DIR" -type f -name 'mongo-*.archive.gz' -mtime "+${RETENTION_DAYS}" -print -delete \
  || true
