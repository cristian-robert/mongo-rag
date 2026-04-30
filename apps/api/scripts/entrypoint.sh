#!/usr/bin/env bash
set -euo pipefail

case "${PROCESS_TYPE:-api}" in
  api)
    exec uvicorn src.main:app --host 0.0.0.0 --port 8100
    ;;
  worker)
    exec celery -A src.worker.celery_app worker --loglevel=info --concurrency=2
    ;;
  *)
    echo "ERROR: unknown PROCESS_TYPE=${PROCESS_TYPE}" >&2
    echo "Valid values: api, worker" >&2
    exit 1
    ;;
esac
