# Architecture Decision Log

Records of significant architectural choices and their rationale.
Added by architect-agent RECORD when structural decisions are made.

## Format

### ADR-NNN: [Decision Title]

**Date:** YYYY-MM-DD
**Status:** Accepted / Superseded by ADR-XXX
**Context:** Why was this decision needed?
**Decision:** What was decided?
**Consequences:** What are the implications (positive and negative)?

---

### ADR-001: BlobStore URI handoff between API and Celery worker

**Date:** 2026-05-01
**Status:** Accepted
**Context:** Issue #79 split the FastAPI app and the Celery worker onto separate Fly Machines. The previous handoff (FastAPI writes to `/tmp`, worker reads same path) silently failed cross-host. Bug A: cross-host `/tmp` mismatch. Bug B: `read_document`/`_transcribe_audio` swallowed Docling/audio failures and returned `[Error:…]` placeholder strings that were chunked and embedded as if they were document text.
**Decision:** Adopt a `BlobStore` Protocol (`apps/api/src/services/blobstore/`) with `put`/`get_stream`/`delete`/`signed_url`. Two implementations — `FilesystemBlobStore` (`file://`) for dev/tests, `SupabaseBlobStore` (`supabase://`, S3-compatible) for prod. Factory (`get_blob_store()`) reads `BLOB_STORE` env at startup. Celery payload carries `blob_uri:` (never `temp_path:`). Worker calls `_assert_tenant_owns_uri` before any I/O, streams blob into a local tmpfile, deletes the blob on success or terminal failure, retains on retryable errors. Supabase bucket has a 24h lifecycle policy as orphan safety net. Bug B fix shipped together: `read_document` and `_transcribe_audio` now raise instead of returning placeholder strings.
**Consequences:**
- (+) Single read path, single URI grammar across dev and prod.
- (+) Tenant assertion is the security boundary, not bucket ACLs — works identically for both schemes.
- (+) Failure modes split cleanly: `blob_read_failed` (infra) vs `docling_failed` (caller input).
- (+) Streaming both ends supports >50MB uploads without memory pressure.
- (-) `signed_url` is on the Protocol but unused by ingestion (kept for future browser read paths).
- (-) Settings additions: `BLOB_STORE`, `SUPABASE_STORAGE_BUCKET`, `SUPABASE_S3_REGION`. `UPLOAD_TEMP_DIR` default changed from `/tmp/...` to `./.tmp/uploads`.
- See `[[decision-blobstore-handoff]]` for the alternatives that were rejected (signed-URL + read-only/write-only client split).

**Verified files:**
- `apps/api/src/services/blobstore/{__init__,base,filesystem,supabase,factory,uri}.py`
- `apps/api/src/routers/ingest.py` (commit `6f33b86`)
- `apps/api/src/worker.py` (commits `b2de07f`, `474f1f5`)
- `apps/api/src/services/ingestion/ingest.py` (Bug B fix in commit `c0ffd6a`)
- `apps/api/src/core/settings.py` (commit `ac819f2`)

---

### ADR-002: Vercel + Fly + Upstash + Supabase Storage deploy

**Date:** 2026-05-01
**Status:** Accepted
**Context:** Issue #79 needed to take the API out of single-host development and split FastAPI from Celery worker. Constraints: two process groups from one image, free idle tier (pre-revenue), low ops surface, must work with existing Supabase Postgres + Atlas Mongo.
**Decision:** Vercel for `apps/web` (native Next.js). Fly Machines for both API (`mongorag-api`, always-on, `min_machines_running=1`) and Worker (`mongorag-worker`, `auto_stop_machines="stop"`, `auto_start_machines=true`, `min_machines_running=0`) — both from a single `apps/api/Dockerfile`, switched by `PROCESS_TYPE=api|worker` env var via `scripts/entrypoint.sh`. Two `fly.toml` files co-located at `apps/api/` so the toml's directory is the Docker build context (Option B). Upstash Redis for the broker (TLS-only `rediss://`, generous free tier). Supabase Storage for blob handoff (already on Supabase Postgres; same project, same key, S3-compatible).
**Consequences:**
- (+) Two Fly Machines from one image; no registry sprawl, no duplicated build pipeline.
- (+) Idle prod ~$5/mo (Vercel domain only); steady SaaS $110-130/mo.
- (+) `scripts/fly-secrets.sh` pushes `apps/api/.env` to both apps in one shot; `scripts/setup_supabase_storage.py` provisions bucket + 24h lifecycle.
- (-) Worker autoscale gap: Fly autostarts on inbound network traffic, but Celery jobs arrive via Redis poll. A cold-stopped worker won't wake on `delay()`. Mitigation: bump `min_machines_running=1` if cold-start is unacceptable, or rely on a future Fly Machines API pinger (out of scope for #79).
- See `[[decision-deploy-fly-vercel]]` for the rejection rationale on Render/Railway.

**Verified files:**
- `apps/api/Dockerfile`, `apps/api/scripts/entrypoint.sh`
- `apps/api/fly.api.toml`, `apps/api/fly.worker.toml`
- `scripts/fly-secrets.sh`, `scripts/setup_supabase_storage.py`
- `apps/web/vercel.ts`, `apps/web/middleware.ts` (CSP `connect-src` extended to `https://mongorag-api.fly.dev`)
- Runbook: `docs/deploy.md`

---
