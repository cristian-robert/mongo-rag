---
title: "Decision: BlobStore handoff between API and Celery worker"
type: decision
tags: [decision, ingestion, blobstore, architecture, celery]
created: 2026-05-01
updated: 2026-05-01
related:
  - "[[concept-celery-ingestion-worker]]"
  - "[[feature-document-ingestion]]"
  - "[[concept-ssrf-defense-url-ingestion]]"
status: compiled
---

## Summary

API and Celery worker hand uploaded files between processes via a `BlobStore` Protocol that emits `scheme://bucket/key` URIs (`file://…` in dev, `supabase://…` in prod). The previous design — FastAPI writes to `/tmp` and the worker reads back the path — works only on a single host and broke as soon as the worker moved to its own Fly Machine. This article records why the URI handoff with a uniform SDK was chosen over signed URLs.

## Context

Two bugs surfaced once the worker was deployed as a separate Fly Machine (issue #79):

- **Bug A — cross-host `/tmp`.** API would write the upload to `/tmp/<uuid>`, dispatch a Celery job carrying `temp_path="/tmp/<uuid>"`, and the worker (different filesystem) would `FileNotFoundError`. Manifested as silent ingestion failure on every prod upload.
- **Bug B — silent placeholder fallback.** When Docling raised on a malformed PDF, `read_document` swallowed the exception and returned the literal string `"[Error: <repr>]"`. That string was chunked, embedded, and persisted as if it were document text — so failed ingestions looked successful, with garbage in `chunks.content`.

Two structural fixes were needed: a real cross-process handoff, and removal of the placeholder fallback so failures fail loudly.

## Decision

Adopt **Approach C: uniform SDK Protocol** with these properties:

- **`BlobStore` Protocol** in `apps/api/src/services/blobstore/base.py` exposes `put`, `get_stream`, `delete`, `signed_url` (declared but unused by ingestion — kept on the interface so future read paths from the browser can use it without reshaping the type).
- **`scheme://bucket/key` URIs** carried in the Celery payload as `blob_uri:`, never `temp_path:`. Schemes: `file://` for `FilesystemBlobStore` (local dev, tests), `supabase://` for `SupabaseBlobStore` (prod, S3-compatible).
- **Streaming both ends.** `put` accepts an async iterator of bytes; `get_stream` returns one. Worker writes the stream to a local tmpfile only after the tenant assertion succeeds.
- **Single read path.** `_assert_tenant_owns_uri(blob_uri, tenant_id)` runs before any `open()`. URIs are parsed once via `services/blobstore/uri.py`; the bucket key is required to start with `<tenant_id>/`.
- **App-level delete + Supabase 24h lifecycle.** Worker deletes the blob on terminal success/failure. Supabase bucket has a 24h expiration policy as a safety net — covers crashes between download and delete, and orphan blobs from cancelled uploads.
- **Bug B fix shipped together.** `services/ingestion/ingest.py::read_document` and `_transcribe_audio` no longer return `[Error:…]` placeholders. They raise; Celery's existing retry/terminal-failure logic handles the rest.

## Trade-offs Considered

**Signed URLs (Approach A — rejected.)** API mints a presigned URL, worker downloads via HTTP. Rejected for three reasons:

1. **TTL race.** A 60s TTL is fine for the happy path, but the worker may sit in Redis for minutes if autostop is on. Re-minting from the worker requires giving the worker the same admin token the API uses, defeating least-privilege.
2. **Dev complexity.** Local dev has no Supabase Storage; faking signed URLs against a filesystem bucket adds branching at every read site.
3. **No streaming.** Most signed-URL SDKs return the whole body or a file path, not an async iterator. Streaming is required for large uploads (>50MB PDFs, audio).

**Two stores, two clients (Approach B — rejected.)** API uses a write-only client; worker uses a read-only client. Rejected because the Protocol abstraction already provides that boundary at the type level (worker code doesn't import `put`), and splitting the SDK doubles the surface area we have to keep in sync between dev and prod.

## Outcome

- One read path, one write path, one URI grammar across dev and prod.
- Tenant assertion is the security boundary, not bucket ACLs — the same check works for `file://` and `supabase://`.
- Observability split into two distinct failure modes: `blob_read_failed` (handoff broken — infra issue) vs `docling_failed` (document broken — caller issue). Bug B made these indistinguishable; the fix restores the distinction.
- Settings additions: `BLOB_STORE`, `SUPABASE_STORAGE_BUCKET`, `SUPABASE_S3_REGION`. Default `BLOB_STORE=filesystem`, `UPLOAD_TEMP_DIR=./.tmp/uploads` (was `/tmp/...`).

## Key Takeaways

- The Celery payload carries `blob_uri:`, never a filesystem path. Anything that looks like `/tmp/` in a task signature is a regression.
- `_assert_tenant_owns_uri` is non-skippable — it runs before `get_stream`, before `open()`, before any I/O.
- Failures raise. No `[Error:…]` strings, ever. Loud failure is the contract.
- 24h Supabase lifecycle is a safety net for orphans, not a substitute for app-level delete.

## See Also

- [[concept-celery-ingestion-worker]] — task definitions and dispatch
- [[feature-document-ingestion]] — full pipeline
- [[concept-ssrf-defense-url-ingestion]] — URL ingestion path that also writes through `BlobStore.put`
- [[decision-deploy-fly-vercel]] — why the worker is a separate Machine in the first place
