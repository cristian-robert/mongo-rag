---
title: "Celery + Redis ingestion worker"
type: concept
tags: [concept, ingestion, celery, redis, async, worker]
sources:
  - "apps/api/src/worker.py"
  - "apps/api/src/routers/ingest.py"
  - "apps/api/src/services/ingestion/"
related:
  - "[[feature-document-ingestion]]"
  - "[[concept-ssrf-defense-url-ingestion]]"
  - "[[decision-blobstore-handoff]]"
created: 2026-04-30
updated: 2026-05-01
status: compiled
---

## Overview

Document and URL ingestion run as Celery tasks against a Redis broker, not as inline FastAPI background tasks. Each task wraps the async ingestion pipeline with `asyncio.run()` so the same code can be unit-tested directly.

## Content

### Configuration (`apps/api/src/worker.py:13-28`)

- Broker AND result backend: `settings.redis_url`
- Serializer: JSON only — Python-bytecode serializers are disabled (no arbitrary deserialization attack surface)
- `task_acks_late = True` — ack only after successful completion (failed worker = redelivered task)
- `worker_prefetch_multiplier = 1` — strict serial processing per worker
- Task tracking enabled

### Tasks

**`ingest_document`** (`worker.py:33-222`)
- Trigger: `routers/ingest.py` after upload is streamed through `BlobStore.put` and document row created with `status="pending"`
- Calls `_assert_tenant_owns_uri(blob_uri, tenant_id)`, then `BlobStore.get_stream(blob_uri)` into a local tmpfile
- Reads doc via Docling, chunks (HybridChunker, max 512 tokens), embeds in batches of 100 against `text-embedding-3-small`, inserts to Mongo `chunks`, flips document `status="ready"`
- Audio formats (`.mp3`, `.wav`, `.m4a`, `.flac`) take a Whisper ASR fallback path
- `max_retries=3`, autoretry on `ConnectionError` / `OSError`, backoff 10s → 90s
- Cleanup: blob deleted on success or terminal failure; retained on retryable errors (so the next attempt still has the bytes); 24h Supabase lifecycle as a safety net for orphans

**`ingest_url`** (`worker.py:225-462`)
- Trigger: `routers/ingest.py` after `validate_url` passes synchronously at the endpoint
- Calls `fetch_url(url, settings)` from `services/ingestion/url_loader.py` — see `[[concept-ssrf-defense-url-ingestion]]` for the full validation set re-run on every redirect
- Writes the fetched response through `BlobStore.put` (same handoff as file uploads), then streams it back via `get_stream` into a local tmpfile, then runs the same Docling → chunk → embed → persist pipeline
- HTML-to-markdown fallback if Docling can't handle the response
- `max_retries=2`, autoretry on `ConnectionError`, backoff 15s → 120s

### Dispatch from FastAPI

Inside the request handler:

```python
task = ingest_document.delay(document_id=str(doc.id), tenant_id=tenant_id, blob_uri=blob_uri, ...)
```

The Celery payload carries `blob_uri:` (e.g. `supabase://mongorag-uploads/<tenant>/<uuid>` or `file://...` in dev), never a filesystem path — see `[[decision-blobstore-handoff]]`. The endpoint returns immediately with `status="pending"`. The web frontend polls `GET /api/v1/documents/{id}/status` (or refreshes the documents list) to discover when the worker has flipped status to `"ready"` or `"failed"`.

### Why Celery (not FastAPI BackgroundTasks)

- Survival across worker restarts (BackgroundTasks die with the process)
- Per-task retry configuration with exponential backoff
- Independent scaling: ingestion workers can scale separately from API replicas
- Strict serialization control (JSON-only) — no native-Python deserialization attack surface

### Operational notes

- Tasks run inside the worker process, not in FastAPI replicas. The API container does not run a worker.
- Redis is the single point of dependency for ingestion progress; outage stalls ingestion but not chat.
- Vector / Atlas Search index changes are NOT done by tasks — apply via Atlas UI or `apps/api/scripts/setup_indexes.py`.

## Key Takeaways

- Ingestion is Celery + Redis, not FastAPI BackgroundTasks.
- JSON serializer only; native-Python serialization disabled.
- `task_acks_late=True` + `prefetch_multiplier=1` = at-least-once semantics, no concurrent processing per worker.
- File ingestion: 3 retries / 10–90s backoff. URL ingestion: 2 retries / 15–120s backoff.
- Endpoints return `status="pending"`; clients poll the document status endpoint.

## See Also

- [[feature-document-ingestion]] — broader pipeline
- [[concept-ssrf-defense-url-ingestion]] — what the URL task re-validates per redirect hop
- [[decision-blobstore-handoff]] — why the payload carries `blob_uri:`, not `temp_path:`
