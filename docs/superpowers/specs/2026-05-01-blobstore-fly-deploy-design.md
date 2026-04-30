# BlobStore Ingestion Handoff + Fly Machines Deploy — Design Spec

- **Issue:** [#79](https://github.com/cristian-robert/mongo-rag/issues/79)
- **Branch:** `feat/79-blobstore-fly-deploy` (off `main`)
- **Mode:** Superpowers
- **Status:** Approved (pending user review of this document)
- **Date:** 2026-05-01

## Goal

Replace the broken filesystem-path ingestion handoff between FastAPI and the Celery worker with an object-storage-backed `BlobStore` abstraction, fix the silent ingestion-corruption bug (Bug B), and ship the production deploy story (Vercel + Fly Machines + Upstash + Supabase Storage). Local dev must remain offline, fast, and cloud-credential-free.

## Background — the bugs we are closing

### Bug A: filesystem split between API and worker

`apps/api/src/routers/ingest.py:138-143` writes uploads to `/tmp/mongorag-uploads/<uuid>/<source>` and dispatches the **path string** to a Celery task. `apps/api/src/worker.py:41-222` reads that path. This works only when the API and worker share `/tmp`. In `docker-compose.dev.yml` and any non-single-host topology (including the planned Fly deploy) it fails: Docling's `DocumentConverter.convert(<path>)` ultimately calls `Path(source).read_bytes()` and raises `FileNotFoundError`.

### Bug B: silent corruption in the read fallback

`apps/api/src/services/ingestion/ingest.py:238-242` swallows the resulting `FileNotFoundError` with a bare `except Exception:` and returns the literal string `"[Error: Could not read file <name>]"`. The pipeline then chunks → embeds → stores that placeholder, marks the document `ready` with `chunk_count=1`, and the system "successfully" persists garbage that pollutes RAG retrieval. Verifiable: any affected document has a single chunk whose content matches `"[Error: Could not read file"`.

## Locked decisions (from brainstorming, 2026-05-01)

| Decision | Choice | Why |
|---|---|---|
| Worker handoff shape | **Approach C** — uniform SDK Protocol with `signed_url` declared but unused by ingestion | Avoids signed-URL TTL race for long Docling jobs; keeps local dev trivial; declares `signed_url` for future browser-direct downloads without forcing it into the worker path |
| URI scheme | **`scheme://bucket/key`** — `supabase://{bucket}/{key}` and `file:///{abs_path}` | Self-describing, trivial tenant-prefix check, no registry table required |
| Streaming | **Stream both ends** — AsyncIterator-based Protocol | Constant memory regardless of file size; survives future cap raises (audio, large PDFs) without a refactor |
| Delete semantics | **App-level delete on success + terminal failure**, 24h Supabase Storage lifecycle rule as safety net | Matches issue acceptance criteria; minimizes orphan footprint; lifecycle rule covers worker crashes / OOM kills |

Out of scope (deferred to follow-up issues): per-tenant blob lifecycle policies, multi-region deploys, Fly rolling-release tuning, advanced worker autoscaler, migrating already-corrupted chunks (Bug B casualties).

## Architecture overview

```
┌──────────┐  PUT /ingest    ┌──────────────┐  blob_store.put()   ┌──────────────────────┐
│  Client  │────────────────▶│ FastAPI (Fly)│────────────────────▶│ BlobStore (s3 / fs)  │
└──────────┘                 │              │                     └──────────────────────┘
                             │  Celery      │
                             │  delay({uri})│
                             └──────┬───────┘
                                    │
                                    ▼
                             ┌──────────────┐  blob_store.open(uri)   ┌──────────────────────┐
                             │ Celery worker│────────────────────────▶│ BlobStore            │
                             │   (Fly)      │                         └──────────────────────┘
                             │              │  → tempfile → Docling → chunks → Mongo
                             │              │  blob_store.delete(uri) on success/terminal
                             └──────────────┘
```

The Celery payload carries a **URI**, never a filesystem path. The deploy topology is no longer an assumption baked into the code.

## Module layout

New module: `apps/api/src/services/blobstore/`

```
services/blobstore/
├── __init__.py     # exports BlobStore, get_blob_store(), BlobStoreError, BlobNotFoundError, BlobAccessError
├── base.py         # BlobStore Protocol, errors, _sanitize_filename, _assert_tenant_owns_uri
├── filesystem.py   # FilesystemBlobStore (file:// scheme)
├── supabase.py     # SupabaseBlobStore (supabase:// scheme; boto3 against S3-compatible endpoint)
└── factory.py      # get_blob_store() — reads BLOB_STORE env, returns process-local singleton
```

## BlobStore Protocol

```python
from typing import AsyncContextManager, AsyncIterator, BinaryIO, Protocol

class BlobStore(Protocol):
    async def put(
        self,
        key: str,
        source: BinaryIO | AsyncIterator[bytes],
        content_type: str | None = None,
    ) -> str:
        """Stream `source` to `key`. Returns the URI (e.g. supabase://bucket/key, file:///abs)."""

    def open(self, uri: str) -> AsyncContextManager[AsyncIterator[bytes]]:
        """Stream bytes back. Raises BlobNotFoundError on 404, BlobAccessError on transient 5xx/network."""

    async def delete(self, uri: str) -> None:
        """Idempotent. Logs but never raises on Supabase errors — lifecycle rule is the safety net."""

    async def signed_url(self, uri: str, expires_in: int = 3600) -> str:
        """Declared in Protocol; not called by ingestion. Reserved for future dashboard download."""
```

### Error model

| Error | Trigger | Worker behavior |
|---|---|---|
| `BlobNotFoundError` | 404 from Supabase, `FileNotFoundError` from fs | **Terminal** — document marked `failed`, blob delete attempted, no retry |
| `BlobAccessError` | Transient 5xx, network, timeout | **Retryable** — Celery retries via existing 10–90s backoff |
| `BlobStoreError` | Base class for both above | n/a |

## URI scheme & tenant isolation

- `SupabaseBlobStore.put` returns `supabase://{bucket}/{tenant_id}/{document_id}/{filename}`
- `FilesystemBlobStore.put` returns `file://{abs_path}` where the path is `{UPLOAD_TEMP_DIR}/{tenant_id}/{document_id}/{filename}`
- Worker dispatches via `urllib.parse.urlparse(uri).scheme` → singleton from `get_blob_store()`
- **Security boundary:** `_assert_tenant_owns_uri(uri, tenant_id)` runs before any `open()` call in the worker. For `supabase://` it parses the path, drops the bucket, and verifies the first segment equals `tenant_id`. For `file://` it verifies the absolute path starts with `{UPLOAD_TEMP_DIR}/{tenant_id}/`. This is the line that prevents a poisoned/replayed Celery message from cross-tenant reading. Unit-tested with explicit cross-tenant URI rejection cases.

### Filename sanitization

Centralized in `services/blobstore/base._sanitize_filename(name)`:

- Strip path traversal sequences (`..`, `/`, `\`)
- Normalize unicode (NFKC)
- Cap length at 255 chars
- Reject empty strings post-sanitization

All `put` callers (`routers/ingest.py` file upload, URL ingestion via `url_loader.py`) go through this helper. Path-traversal guard at the API edge stays as defense-in-depth.

## Settings (`apps/api/src/core/settings.py`)

```python
BLOB_STORE: Literal["fs", "supabase"] = "fs"
SUPABASE_STORAGE_BUCKET: str | None = None  # required when BLOB_STORE="supabase"
UPLOAD_TEMP_DIR: str = "./.tmp/uploads"     # used by FilesystemBlobStore
SUPABASE_S3_REGION: str = "us-east-1"       # boto3 needs a region; Supabase ignores it
```

`get_blob_store()` raises at startup if `BLOB_STORE="supabase"` and (`SUPABASE_STORAGE_BUCKET` or `SUPABASE_SECRET_KEY`) is missing. Fail-fast in `scripts/dev.sh` mirrors the same check.

## Hot path changes

### `apps/api/src/routers/ingest.py`

```python
async def ingest_file(
    file: UploadFile,
    principal: Principal = Depends(get_principal),
    blob_store: BlobStore = Depends(get_blob_store),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    _enforce_size_cap(file)                                           # MAX_UPLOAD_SIZE_MB pre-I/O
    safe_name = _sanitize_filename(file.filename)
    document = await _create_document_pending(db, principal, safe_name)  # status="uploading"

    key = f"{principal.tenant_id}/{document.id}/{safe_name}"
    try:
        uri = await blob_store.put(key, file.file, file.content_type)
    except Exception:
        await _mark_document_failed(db, principal, document.id, "blob_upload_failed")
        raise HTTPException(500, "upload failed")

    await _mark_document_status(db, principal, document.id, "queued")
    task = ingest_document.delay(
        document_id=str(document.id),
        tenant_id=str(principal.tenant_id),
        blob_uri=uri,
    )
    return {"document_id": str(document.id), "task_id": task.id}
```

URL-ingestion path (`ingest_url`): unchanged SSRF defense via `services/ingestion/url_loader.py`, then write fetched bytes through `BlobStore.put` so the worker has a single read path.

### `apps/api/src/worker.py`

```python
@celery_app.task(bind=True, max_retries=3, default_retry_delay=10, acks_late=True)
def ingest_document(self, *, document_id: str, tenant_id: str, blob_uri: str):
    blob_store = get_blob_store()
    _assert_tenant_owns_uri(blob_uri, tenant_id)

    try:
        asyncio.run(_run(document_id, tenant_id, blob_uri, blob_store))
        asyncio.run(_safe_delete(blob_store, blob_uri))
    except BlobNotFoundError as e:
        asyncio.run(_mark_failed(document_id, tenant_id, f"blob_not_found: {e}"))
        asyncio.run(_safe_delete(blob_store, blob_uri))
        raise
    except BlobAccessError as e:
        raise self.retry(exc=e)
    except RetryableIngestionError as e:
        raise self.retry(exc=e)
    except Exception as e:
        asyncio.run(_mark_failed(document_id, tenant_id, str(e)))
        asyncio.run(_safe_delete(blob_store, blob_uri))
        raise

async def _run(document_id, tenant_id, blob_uri, blob_store):
    ext = _ext_from_uri(blob_uri)
    async with blob_store.open(blob_uri) as stream:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as dst:
            async for chunk in stream:
                dst.write(chunk)
            tmp_path = dst.name
    try:
        await _existing_pipeline(tmp_path, document_id, tenant_id)
    finally:
        os.unlink(tmp_path)
```

`_safe_delete` swallows + logs Supabase delete errors; success of the ingestion is never blocked by cleanup hiccups.

### Bug B fix — `apps/api/src/services/ingestion/ingest.py`

Remove the silent fallback in lines 238–242:

```python
# DELETE:
try:
    with open(file_path, "r", encoding="utf-8") as f:
        return (f.read(), None)
except Exception:
    return (f"[Error: Could not read file {os.path.basename(file_path)}]", None)
```

Replace with:

```python
def _read_text_fallback(file_path: str) -> tuple[str, None]:
    """Used when Docling can't parse a format. Reads as utf-8 plain text."""
    with open(file_path, "r", encoding="utf-8") as f:
        return (f.read(), None)
```

No `try/except`. `read_document` and the surrounding Docling fallback chain are audited for any other `except Exception:` swallows; each must propagate or raise a typed retryable/non-retryable error.

### Document status state machine

```
uploading  → queued     (after blob_store.put succeeds, before celery dispatch)
queued     → processing (worker picks up task)
processing → ready      (chunks stored, blob deleted)
processing → failed     (terminal error, blob deleted, error_message set)
```

All transitions are tenant-scoped writes via existing `tenant_filter` helpers.

### Delete semantics

| Trigger | Delete blob? | Why |
|---|---|---|
| Ingestion success | Yes (immediate) | Issue AC; minimize storage cost |
| Retryable failure (`BlobAccessError`, transient Docling) | No | Next retry needs the blob |
| Terminal failure (`BlobNotFoundError`, retries exhausted, non-retryable) | Yes (immediate) | Issue AC; no future use |
| Worker crash / OOM mid-task | No (no chance to delete) | 24h Supabase lifecycle rule cleans up |
| `delete()` itself fails (Supabase 5xx) | Logged + metric, ignored | 24h Supabase lifecycle rule cleans up |

## Observability

One structured log line per ingestion outcome:

```python
log.info("ingestion_complete", extra={
    "document_id": document_id,
    "tenant_id": tenant_id,
    "blob_uri": blob_uri,
    "blob_size_bytes": size,
    "status": "ready" | "failed",
    "chunks": chunk_count,
    "duration_ms": elapsed,
    "blob_read_failed": False,    # True only on BlobNotFoundError or BlobAccessError
    "docling_failed": False,      # True if Docling raised
})
```

The `blob_read_failed` vs `docling_failed` split is the explicit Bug A regression detector. A spike in `blob_read_failed` indicates a topology / credential / RLS regression; a spike in `docling_failed` indicates a content / format issue.

## Deploy: Fly Machines + Vercel + Upstash + Supabase Storage

### Single Dockerfile, two process groups

```dockerfile
# apps/api/Dockerfile (additions)
ENV PROCESS_TYPE=api
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["tini", "--", "/entrypoint.sh"]
```

```bash
# scripts/entrypoint.sh
#!/usr/bin/env bash
set -euo pipefail
case "${PROCESS_TYPE:-api}" in
  api)    exec uvicorn src.main:app --host 0.0.0.0 --port 8100 ;;
  worker) exec celery -A src.worker.celery_app worker --loglevel=info --concurrency=2 ;;
  *)      echo "unknown PROCESS_TYPE=$PROCESS_TYPE" >&2; exit 1 ;;
esac
```

### `fly.api.toml`

```toml
app = "mongorag-api"
primary_region = "iad"

[build]
  dockerfile = "apps/api/Dockerfile"

[env]
  PROCESS_TYPE = "api"
  PORT = "8100"

[http_service]
  internal_port = 8100
  force_https = true
  auto_stop_machines = "off"
  min_machines_running = 1

[[vm]]
  cpu_kind = "shared"
  cpus = 1
  memory_mb = 512
```

### `fly.worker.toml`

```toml
app = "mongorag-worker"
primary_region = "iad"

[build]
  dockerfile = "apps/api/Dockerfile"

[env]
  PROCESS_TYPE = "worker"

[deploy]
  strategy = "rolling"

[[vm]]
  cpu_kind = "shared"
  cpus = 2
  memory_mb = 1024

[machine]
  auto_stop_machines = "stop"
  auto_start_machines = true
  min_machines_running = 0
```

### Worker autoscale strategy

Fly does not natively know Celery queue depth. We trigger worker wake from the API on dispatch via the Fly Machines API (`fly machines start mongorag-worker` — equivalent REST call from the API process). Trade-off: ~5–10s cold-start latency on the first task after idle; acceptable for ingestion (already async, user sees `queued` immediately). Documented in `docs/deploy.md`; tuning out of scope for #79.

### Fly secrets — `scripts/fly-secrets.sh`

```bash
#!/usr/bin/env bash
# Sync secrets from local .env to both Fly apps.
# Usage: ./scripts/fly-secrets.sh [api|worker|both]
set -euo pipefail
SECRETS=(
  MONGODB_URI DATABASE_URL
  SUPABASE_URL SUPABASE_SECRET_KEY SUPABASE_JWT_SECRET SUPABASE_STORAGE_BUCKET
  LLM_API_KEY EMBEDDING_API_KEY
  STRIPE_SECRET_KEY STRIPE_WEBHOOK_SECRET
  REDIS_URL
  BLOB_STORE
)
# resolves each from env, calls `fly secrets set --app mongorag-{api,worker}` accordingly
```

### Vercel — `apps/web/vercel.ts`

```ts
import { type VercelConfig } from '@vercel/config/v1';

export const config: VercelConfig = {
  framework: 'nextjs',
  buildCommand: 'pnpm build',
  installCommand: 'pnpm install',
};
```

`NEXT_PUBLIC_API_URL` set per-environment in Vercel project settings (committed `vercel.ts` carries no secrets). CSP `connect-src` in `apps/web/next.config.ts` extended to include `https://mongorag-api.fly.dev`.

### Supabase Storage configuration

- Bucket: `mongorag-uploads`, **private** (no public read)
- Lifecycle rule: delete objects older than 24 hours (configured via `scripts/setup_supabase_storage.py` or Supabase dashboard — script preferred for reproducibility)
- RLS: deny-all by default; service role bypass (the API and worker authenticate with `SUPABASE_SECRET_KEY`)
- Tenant isolation: enforced via key prefix `{tenant_id}/{document_id}/{filename}` and worker-side `_assert_tenant_owns_uri`

## Local dev

### `docker-compose.dev.yml`

```yaml
services:
  worker:
    build:
      context: .
      dockerfile: apps/api/Dockerfile
    environment:
      PROCESS_TYPE: worker
      BLOB_STORE: fs
      UPLOAD_TEMP_DIR: /workspace/.tmp/uploads
    volumes:
      - ./.tmp/uploads:/workspace/.tmp/uploads:rw
```

API runs on the host via `scripts/dev.sh` with `UPLOAD_TEMP_DIR=$PWD/.tmp/uploads` and `BLOB_STORE=fs`. Bind mount lets host-side API and containerized worker resolve identical `file:///abs-path` URIs.

`.tmp/` added to `.gitignore`.

### `docker-compose.yml` (full Docker dev)

Both `api` and `worker` services share a named volume:

```yaml
services:
  api:
    volumes:
      - uploads:/workspace/.tmp/uploads
  worker:
    volumes:
      - uploads:/workspace/.tmp/uploads
volumes:
  uploads:
```

### `scripts/dev.sh` ergonomics

```bash
echo "BLOB_STORE=${BLOB_STORE:-fs}"

if [[ "${BLOB_STORE:-fs}" == "supabase" ]]; then
  : "${SUPABASE_STORAGE_BUCKET:?SUPABASE_STORAGE_BUCKET required when BLOB_STORE=supabase}"
  : "${SUPABASE_SECRET_KEY:?SUPABASE_SECRET_KEY required when BLOB_STORE=supabase}"
fi

mkdir -p "${UPLOAD_TEMP_DIR:-$PWD/.tmp/uploads}"
```

## Test matrix

| Type | Test | Where |
|---|---|---|
| Unit | `FilesystemBlobStore` round-trip via `tmp_path` | `apps/api/tests/unit/blobstore/test_filesystem.py` |
| Unit | `SupabaseBlobStore` against mocked S3 endpoint (`moto` or `botocore.stub.Stubber`) | `apps/api/tests/unit/blobstore/test_supabase.py` |
| Unit | URI parsing + `_assert_tenant_owns_uri` (cross-tenant URI rejected) | `apps/api/tests/unit/blobstore/test_uri.py` |
| Unit | Bug B regression — `read_document` raises on missing file (no placeholder string) | `apps/api/tests/unit/ingestion/test_read_document.py` |
| Integration | Full ingestion happy path with `BLOB_STORE=fs`, real Mongo, real Celery worker | `apps/api/tests/integration/test_ingestion_flow.py` |
| Integration | Missing-blob terminal failure — document ends `status=failed`, `chunk_count=0` | same file |
| Integration | Bug B regression — known-bad input never produces `status=ready, chunk_count=1, content^="[Error:"` | same file |
| Optional | `@pytest.mark.supabase_storage` against real Supabase test bucket (skipped in CI by default) | `apps/api/tests/integration/test_supabase_blobstore.py` |

Plus `uv run ruff check .`, `uv run ruff format --check .`, `pnpm lint` all green before ship.

## Documentation

### New files

- `docs/deploy.md` — Vercel + Fly + Upstash + Supabase Storage walkthrough; secrets list; rollback notes; cost table.
- `.obsidian/wiki/decision-blobstore-handoff.md` — why BlobStore Protocol, why URI scheme, why streaming, why app-level delete.
- `.obsidian/wiki/decision-deploy-fly-vercel.md` — why Fly over Render/Railway, why Vercel for web, why Upstash for Redis, idle-cost analysis.

### Updates

- `docs/architecture.md` — add the BlobStore handoff diagram, update the "ingestion" section.
- `.obsidian/wiki/concept-celery-ingestion-worker.md` — note URI-based handoff, link to `decision-blobstore-handoff`.
- `.obsidian/wiki/feature-document-ingestion.md` — same.
- `.claude/agents/architect-agent/index.md` — add `services/blobstore/` to the Backend Layout table.
- KB indexes rebuilt via `KB_PATH=.obsidian node cli/kb-search.js index`.

## Acceptance criteria (mirrors issue #79, restated for spec completeness)

### Functional

- [ ] Uploaded files reach the worker through `BlobStore` — no path strings cross the Celery boundary.
- [ ] Worker resolves blob URI → temp file → Docling → success path produces real chunked content (NOT a 1-chunk error placeholder).
- [ ] Blob read failure marks the document `failed` with a useful `error_message`. No silent placeholder storage.
- [ ] Successful ingestion deletes the blob; terminal failures delete the blob; transient failures retain it for retry.
- [ ] All existing ingestion endpoints behave the same from the client's perspective (202 + `document_id` + `task_id`).
- [ ] Tenant isolation preserved — blob keys prefixed with `tenant_id`; `_assert_tenant_owns_uri` enforces in the worker; Supabase Storage RLS verified.
- [ ] SSRF defense for the URL ingestion path remains intact.

### Bug B — fail loud

- [ ] `services/ingestion/ingest.py` no longer returns a placeholder string on read failure. Failures raise.
- [ ] Regression test: missing-blob ingestion → document `failed` with `chunk_count=0`, never `ready` with `chunk_count=1`.
- [ ] Regression test: a chunk's `content` field never starts with `"[Error:"`.

### Local dev

- [ ] `scripts/dev.sh` + `docker-compose.dev.yml` ingest end-to-end with `BLOB_STORE=fs`. No Supabase or cloud creds needed.
- [ ] `docker-compose.yml` (full Docker dev) ingestion works with the named volume.
- [ ] `uv run pytest` (unit + integration) passes offline.
- [ ] `scripts/dev.sh` prints active `BLOB_STORE` and fails fast on missing prod credentials when `BLOB_STORE=supabase`.

### Production deploy

- [ ] `fly.api.toml` and `fly.worker.toml` committed.
- [ ] API process group: ≥1 always-on.
- [ ] Worker process group: `auto_stop_machines = "stop"`, `min_machines_running = 0`, autostart strategy documented.
- [ ] Single `apps/api/Dockerfile` produces an image used by both groups; entrypoint switches on `PROCESS_TYPE`.
- [ ] Fly secrets documented in `docs/deploy.md`.
- [ ] Vercel project for `apps/web` linked; `NEXT_PUBLIC_API_URL` points at the Fly API hostname; CSP allows it.
- [ ] Smoke deploy: real PDF uploaded in prod end-to-end, verified chunks (>1, content matches document).

### Observability + safety rails

- [ ] Structured log on every ingestion: `{document_id, tenant_id, blob_uri, blob_size, status}`.
- [ ] `blob_read_failed` vs `docling_failed` distinguishable in logs.
- [ ] Upload size capped via `MAX_UPLOAD_SIZE_MB` before `BlobStore.put`.
- [ ] Filename sanitization centralized in `services/blobstore/base._sanitize_filename`.

### Tests (mandatory before /ship)

- [ ] Unit + integration matrix above all passing.
- [ ] `uv run ruff check .`, `uv run ruff format --check .`, `pnpm lint` all green.

## Files most likely touched

- `apps/api/src/services/blobstore/` — new module (5 files)
- `apps/api/src/services/ingestion/ingest.py` — remove silent fallback, accept blob URI
- `apps/api/src/routers/ingest.py` — write to BlobStore instead of /tmp
- `apps/api/src/worker.py` — resolve URI in task, tenant assertion, delete semantics
- `apps/api/src/core/settings.py` — `BLOB_STORE`, `SUPABASE_STORAGE_BUCKET`, `UPLOAD_TEMP_DIR`, `SUPABASE_S3_REGION`
- `apps/api/Dockerfile` — `PROCESS_TYPE` entrypoint switch
- `scripts/entrypoint.sh` — new
- `scripts/dev.sh` — env wiring + fail-fast + dir creation
- `scripts/fly-secrets.sh` — new
- `scripts/setup_supabase_storage.py` — new (bucket + lifecycle rule)
- `docker-compose.yml`, `docker-compose.dev.yml` — shared volume / bind mount
- `fly.api.toml`, `fly.worker.toml` — new
- `apps/web/vercel.ts` — new
- `apps/web/next.config.ts` — CSP allowlist update
- `docs/deploy.md` — new
- `.obsidian/wiki/decision-blobstore-handoff.md`, `.obsidian/wiki/decision-deploy-fly-vercel.md` — new
- `.obsidian/wiki/concept-celery-ingestion-worker.md`, `feature-document-ingestion.md` — updated
- `.claude/agents/architect-agent/index.md` — Backend Layout table updated
- `apps/api/tests/unit/blobstore/`, `apps/api/tests/unit/ingestion/test_read_document.py`, `apps/api/tests/integration/test_ingestion_flow.py`, `apps/api/tests/integration/test_supabase_blobstore.py` — new tests
- `.gitignore` — add `.tmp/`

## Implementation outline (high-level)

Detailed task breakdown will be produced by `/plan-feature` after this spec is approved. High-level shape:

1. `architect-agent IMPACT` — capture surface change.
2. TDD `BlobStore` Protocol + `FilesystemBlobStore` — interface stable before any other code moves.
3. TDD `SupabaseBlobStore` against mocked S3 — same interface, Supabase-backed.
4. Migrate router + worker to BlobStore — Bug A fixed.
5. Remove silent fallback in `ingest.py` — Bug B fixed.
6. Add tenant-prefix assertion + observability fields.
7. Compose updates — local dev parity confirmed end-to-end.
8. Dockerfile entrypoint switch + Fly toml files.
9. Vercel `vercel.ts`, CSP update, deployment smoke test.
10. Documentation: `docs/deploy.md`, wiki articles, KB indexes rebuilt, architect-agent index updated.

## Branch + workflow

- Branch: `feat/79-blobstore-fly-deploy` off `main`.
- Mode: Superpowers.
- Pipeline: brainstorm (this doc) → `/plan-feature` → TDD → `/execute` → `/validate` → `/ship`.
- Issue #79 is the source of truth for scope; this spec is the source of truth for design.

## References

- Issue: [#79](https://github.com/cristian-robert/mongo-rag/issues/79)
- Wiki: [[concept-celery-ingestion-worker]], [[concept-ssrf-defense-url-ingestion]], [[concept-principal-tenant-isolation]], [[feature-document-ingestion]], [[decision-postgres-mongo-storage-split]]
- Code: `apps/api/src/routers/ingest.py:138-143` (Bug A), `apps/api/src/services/ingestion/ingest.py:238-242` (Bug B), `apps/api/src/worker.py:41-222` (worker)
