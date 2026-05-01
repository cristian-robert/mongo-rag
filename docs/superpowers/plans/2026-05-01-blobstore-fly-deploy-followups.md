# BlobStore + Fly Deploy — Reviewer Follow-ups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining 5 Medium and 4 Low findings from the adversarial code review of `feat/79-blobstore-fly-deploy` so the branch ships clean. The two Critical and four High findings were already closed in commits 83ba98d, aa1a808, abf5648, 3c2cee0.

**Architecture:** No architectural change. Targeted hardening of existing modules (`worker.py`, `services/blobstore/`, `core/settings.py`) plus shell-script polish. All changes additive or refactor-in-place; no new modules, no schema changes.

**Tech Stack:** FastAPI, Celery, Pydantic Settings, boto3, pytest, bash.

**Original spec:** `docs/superpowers/specs/2026-05-01-blobstore-fly-deploy-design.md`
**Original plan:** `docs/superpowers/plans/2026-05-01-blobstore-fly-deploy.md`
**Issue:** [#79](https://github.com/cristian-robert/mongo-rag/issues/79)
**Branch:** `feat/79-blobstore-fly-deploy` (22 commits ahead of main as of 2026-05-01)

---

## Reviewer findings closed by this plan

| Severity | Issue | Task |
|---|---|---|
| Medium | Case-sensitive `BLOB_STORE` literal | 1 |
| Medium | URI percent-decoding gap on `supabase://` | 2 |
| Medium | `ingest_url` retries re-fetch URL because blob deleted in `finally` | 3 |
| Medium | `ingestion_complete` log inconsistent / missing on URL paths | 4 |
| Medium | Success-path race: READY → FAILED-as-duplicate via retry | 5 |
| Low | `fly-secrets.sh` requires CWD = repo root + `set -x` leak | 6 |
| Low | `setup_supabase_storage.py` exits 0 when lifecycle fails | 7 |
| Low | Nested broad-except in `_safe_delete` / `SupabaseBlobStore.delete` | 8 |
| Low | Integration test reaches into worker module-level state | 9 |

Each task is self-contained and committable independently. Tasks 3–5 and 9 all touch `apps/api/src/worker.py` and should run sequentially to avoid merge conflicts; the rest can run in any order.

---

## Task 1: Accept `BLOB_STORE` case-insensitively

**Files:**
- Modify: `apps/api/src/core/settings.py` (~line 219, the `blob_store` field)
- Test: `apps/api/tests/test_settings.py`

**Background:** `Literal["fs", "supabase"]` is case-sensitive. An operator who sets `BLOB_STORE=Supabase` to "match" `SUPABASE_*` env vars gets a Pydantic validation error before the friendly handler in `load_settings()` runs. The friendly handler only checks for `mongodb_uri`/`llm_api_key`/`embedding_api_key` substrings.

- [ ] **Step 1: Write failing tests**

Append to `apps/api/tests/test_settings.py`:

```python
def test_blob_store_accepts_uppercase(monkeypatch):
    """Case-insensitive: BLOB_STORE=Supabase must work like supabase."""
    monkeypatch.setenv("BLOB_STORE", "Supabase")
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "test-bucket")
    from src.core.settings import Settings
    s = Settings()
    assert s.blob_store == "supabase"


def test_blob_store_accepts_mixed_case(monkeypatch):
    monkeypatch.setenv("BLOB_STORE", "FS")
    from src.core.settings import Settings
    s = Settings()
    assert s.blob_store == "fs"


def test_blob_store_rejects_unknown_value(monkeypatch):
    monkeypatch.setenv("BLOB_STORE", "azure")
    from src.core.settings import Settings
    with pytest.raises(Exception):  # ValidationError
        Settings()
```

- [ ] **Step 2: Run, expect failure** (`cd apps/api && uv run pytest tests/test_settings.py -k "blob_store_accepts" -v`).

- [ ] **Step 3: Add a `field_validator` that lowercases before validation**

In `apps/api/src/core/settings.py`, near the top of imports (after the existing `from pydantic import Field`):

```python
from pydantic import Field, field_validator
```

Inside the `Settings` class, after the `blob_store` field, add:

```python
    @field_validator("blob_store", mode="before")
    @classmethod
    def _normalize_blob_store(cls, v):
        """Accept BLOB_STORE case-insensitively before Literal validation."""
        if isinstance(v, str):
            return v.lower()
        return v
```

- [ ] **Step 4: Run tests, expect pass** (`cd apps/api && uv run pytest tests/test_settings.py -v`).

- [ ] **Step 5: Lint** (`cd apps/api && uv run ruff check apps/api/src/core/settings.py apps/api/tests/test_settings.py && uv run ruff format --check apps/api/src/core/settings.py apps/api/tests/test_settings.py`).

- [ ] **Step 6: Commit** via `/commit` with message `fix(api): accept BLOB_STORE case-insensitively (#79)`.

---

## Task 2: Percent-decode + tighten tenant prefix check on `supabase://`

**Files:**
- Modify: `apps/api/src/services/blobstore/uri.py:assert_tenant_owns_uri`
- Test: `apps/api/tests/test_blobstore_uri.py`

**Background:** `urlparse` does NOT URL-decode the `path` component. If a worker gets dispatched with `supabase://bucket/tenant%2da/doc/file` (URL-encoded `tenant-a`), the prefix check compares `"tenant%2da" != "tenant-a"` and rejects legitimate access. Conversely, if a malformed payload contains `%` or `..` in the tenant segment, the current check doesn't detect it.

- [ ] **Step 1: Write failing tests**

Append to `apps/api/tests/test_blobstore_uri.py` inside `TestAssertTenantOwnsURI`:

```python
    def test_supabase_uri_percent_encoded_tenant_decoded_then_matched(self):
        """%2da → -a; the URI tenant segment must decode before comparison."""
        assert_tenant_owns_uri(
            "supabase://mongorag-uploads/tenant%2da/doc-1/file.pdf",
            "tenant-a",
        )

    def test_supabase_uri_tenant_segment_with_percent_after_decode_rejected(self):
        """A literal % in a tenant id is suspicious — reject."""
        with pytest.raises(InvalidBlobURIError):
            assert_tenant_owns_uri(
                "supabase://mongorag-uploads/%25weird/doc-1/file.pdf",
                "%weird",
            )

    def test_supabase_uri_tenant_segment_with_dotdot_rejected(self):
        with pytest.raises(InvalidBlobURIError):
            assert_tenant_owns_uri(
                "supabase://mongorag-uploads/..upper/doc-1/file.pdf",
                "..upper",
            )

    def test_supabase_uri_tenant_segment_with_null_byte_rejected(self):
        with pytest.raises(InvalidBlobURIError):
            assert_tenant_owns_uri(
                "supabase://mongorag-uploads/tenant%00a/doc-1/file.pdf",
                "tenant\x00a",
            )
```

- [ ] **Step 2: Run, expect failures** (`cd apps/api && uv run pytest tests/test_blobstore_uri.py -v`).

- [ ] **Step 3: Update `assert_tenant_owns_uri` for `supabase://`**

In `apps/api/src/services/blobstore/uri.py`, change the `if parsed.scheme == "supabase":` branch to:

```python
    if parsed.scheme == "supabase":
        # supabase://<bucket>/<tenant>/<doc>/<file>
        # `netloc` is the bucket; `path` is /tenant/doc/file
        from urllib.parse import unquote

        decoded_path = unquote(parsed.path)
        path_parts = decoded_path.lstrip("/").split("/", 1)
        if not path_parts or not path_parts[0]:
            raise InvalidBlobURIError(f"missing tenant segment: {uri}")
        tenant_segment = path_parts[0]
        # Defensive: reject suspicious characters in the tenant segment.
        if any(c in tenant_segment for c in ("/", "..", "%", "\x00")):
            raise InvalidBlobURIError(
                f"unsafe tenant segment {tenant_segment!r} in: {uri}"
            )
        if tenant_segment != tenant_id:
            raise TenantOwnershipError(
                f"tenant mismatch: uri={tenant_segment!r} expected={tenant_id!r}"
            )
        return
```

- [ ] **Step 4: Run tests, expect pass** (`cd apps/api && uv run pytest tests/test_blobstore_uri.py -v`).

- [ ] **Step 5: Lint** (`cd apps/api && uv run ruff check apps/api/src/services/blobstore/uri.py apps/api/tests/test_blobstore_uri.py && uv run ruff format --check apps/api/src/services/blobstore/uri.py apps/api/tests/test_blobstore_uri.py`).

- [ ] **Step 6: Commit** via `/commit` with message `fix(api): percent-decode + tighten supabase:// tenant prefix check (#79)`.

---

## Task 3: Stop deleting URL-fetch blob in `finally` — only on terminal/success

**Files:**
- Modify: `apps/api/src/worker.py` — `ingest_url` task

**Background:** Current `ingest_url` `finally` block always calls `_safe_delete(blob_store, blob_uri)`. When a retry fires, the blob is gone, the next attempt re-fetches the URL. If the URL serves dynamic content (news, paywall), the second attempt may store *different* content than what the user saw. Mirror `ingest_document`: delete on success, duplicate, empty, no-chunks, and terminal-failure paths only — not in `finally`.

- [ ] **Step 1: Read current `ingest_url`**

```bash
grep -n "ingest_url\|_safe_delete\|finally" apps/api/src/worker.py | head -40
```

Locate (a) the `finally` block at the bottom of `_run` for `ingest_url`, (b) every early-return path (success, duplicate, empty, no-chunks), (c) the broad `except Exception` block.

- [ ] **Step 2: Move blob delete out of `finally`**

In the `ingest_url` task's `_run` function:

1. Before each `return {"document_id": ..., "status": "failed", ...}` (the early-failure paths: empty content, duplicate, no-chunks), call `await _safe_delete(blob_store, blob_uri)` if `blob_store is not None and blob_uri is not None`.
2. After the success path's `update_status(READY)` and the success log, call `await _safe_delete(blob_store, blob_uri)`.
3. In the `except Exception as e:` block, follow the same pattern as `ingest_document`: only delete if `_is_terminal_failure(self, e)`.
4. **Remove** the blob delete from the `finally` block. Keep the temp_dir cleanup and `client.close()` in `finally`.

- [ ] **Step 3: Update existing tests if any reference the unconditional delete**

```bash
cd apps/api && grep -rn "ingest_url\|fetched.content\|blob_uri" tests/ | head -20
```

Adjust any test fixtures or assertions; do not invent new tests in this task — Task 4 will add behavioral coverage of the log-line standardization.

- [ ] **Step 4: Run url-related tests** (`cd apps/api && uv run pytest tests/test_url_loader.py tests/test_ingest_router.py -v -k "url"`).

- [ ] **Step 5: Lint** (`cd apps/api && uv run ruff check apps/api/src/worker.py && uv run ruff format --check apps/api/src/worker.py`).

- [ ] **Step 6: Commit** via `/commit` with message `fix(api): only delete URL-fetch blob on success/terminal, not in finally (#79)`.

---

## Task 4: Standardize `ingestion_complete` log line across both ingestion paths

**Files:**
- Modify: `apps/api/src/worker.py` — both `ingest_document` and `ingest_url` task functions

**Background:** Spec required structured `ingestion_complete` on every exit. `ingest_document` emits it on success and on the broad `except`. `ingest_url` emits a different message (`"URL ingestion complete"`) with different fields, and emits NOTHING structured on its failure paths. Observability dashboards keyed on `ingestion_complete` silently miss every URL ingestion.

- [ ] **Step 1: Add a small helper at module level**

In `apps/api/src/worker.py`, near `_safe_delete` and `_is_terminal_failure`:

```python
def _emit_ingestion_complete(
    *,
    document_id: str,
    tenant_id: str,
    blob_uri: str | None,
    blob_size_bytes: int,
    status: str,
    chunks: int,
    blob_read_failed: bool,
    docling_failed: bool,
    source_kind: str,  # "upload" or "url"
) -> None:
    """Single shape for the structured ingestion-outcome log line."""
    task_logger.info(
        "ingestion_complete",
        extra={
            "document_id": document_id,
            "tenant_id": tenant_id,
            "blob_uri": blob_uri,
            "blob_size_bytes": blob_size_bytes,
            "status": status,
            "chunks": chunks,
            "blob_read_failed": blob_read_failed,
            "docling_failed": docling_failed,
            "source_kind": source_kind,
        },
    )
```

- [ ] **Step 2: Replace the inline `task_logger.info("ingestion_complete", ...)` calls** in `ingest_document._run` (success branch and broad-except branch) with `_emit_ingestion_complete(source_kind="upload", ...)`. Verify no field is dropped.

- [ ] **Step 3: Add `_emit_ingestion_complete` calls to every exit path in `ingest_url._run`**:
- After success `update_status(READY)`: status="ready", source_kind="url".
- Each `return {"document_id": ..., "status": "failed", ...}` early-return path (empty, duplicate, no-chunks, fetch-failed): status="failed", chunks=0, with appropriate `blob_read_failed`/`docling_failed` flags.
- The broad `except Exception` block: status="failed", chunks=0, both flags as tracked.

For the URL path, `blob_uri` may be None when fetch failed before put — emit anyway with `blob_uri=None`. `blob_size_bytes` defaults to 0 if not tracked.

- [ ] **Step 4: Search for orphan log lines** in `worker.py`:

```bash
grep -n "ingestion complete\|URL ingestion complete\|task_logger.info" apps/api/src/worker.py
```

Drop any old `"URL ingestion complete: doc=%s tenant=%s url=%s chunks=%d"` style messages — `_emit_ingestion_complete` replaces them.

- [ ] **Step 5: Run unit tests** (`cd apps/api && uv run pytest tests/test_ingest_router.py tests/test_ingestion_service.py tests/test_worker_retry.py -v`).

- [ ] **Step 6: Lint** (`cd apps/api && uv run ruff check apps/api/src/worker.py && uv run ruff format --check apps/api/src/worker.py`).

- [ ] **Step 7: Commit** via `/commit` with message `feat(api): unified ingestion_complete log line across upload + url paths (#79)`.

---

## Task 5: Prevent success-path race that marks READY doc as FAILED-as-duplicate

**Files:**
- Modify: `apps/api/src/worker.py` — `ingest_document._run`

**Background:** Race: `update_status(READY)` succeeds but a later operation in the success branch (e.g., `_safe_delete`, the log emission, the embedder) raises. The broad `except` runs, `_is_terminal_failure` may return False for non-typed Mongo errors, the task retries — and on retry, `check_duplicate` returns the already-stored doc, the worker calls `update_status(FAILED, "Duplicate of existing document")`, overwriting the READY status. Net effect: a successfully ingested doc gets marked failed by its own retry.

The same risk theoretically exists for `ingest_url` post-`update_status(READY)`.

- [ ] **Step 1: Add a `committed` flag in both `_run` functions**

In `ingest_document._run`, before the try block:

```python
        committed = False  # True after update_status(READY) lands
```

In the success path, set it after `update_status(READY)` returns successfully:

```python
            await service.update_status(
                document_id, tenant_id, DocumentStatus.READY, ...
            )
            committed = True
```

- [ ] **Step 2: Guard the broad except**

In the broad `except Exception as e:` block in `ingest_document._run`:

```python
        except Exception as e:
            if committed:
                # Post-success exception (e.g., delete or log failed). Do NOT
                # mark the document failed — it was already persisted READY.
                # Lifecycle rule will catch any leaked blob.
                task_logger.warning(
                    "post_success_exception",
                    extra={
                        "document_id": document_id,
                        "tenant_id": tenant_id,
                        "exc": type(e).__name__,
                        "msg": str(e)[:200],
                    },
                )
                return {
                    "document_id": document_id,
                    "status": "ready",
                    "chunk_count": ...,  # use the same value passed to update_status
                }
            # ... existing pre-success failure handling ...
```

The `chunk_count` in the post-success return needs to be in scope — track it in a `chunk_count: int = 0` variable that gets updated when the chunks land.

- [ ] **Step 3: Apply the same pattern to `ingest_url._run`** — track `committed` and guard its broad except identically.

- [ ] **Step 4: Add a regression test** to `apps/api/tests/test_worker_retry.py`:

```python
def test_post_success_exception_does_not_mark_failed(monkeypatch, tmp_path):
    """Regression: if cleanup/log raises after update_status(READY),
    the doc must NOT be flipped to FAILED on the same call."""
    # Strategy: monkeypatch _safe_delete to raise. Drive ingest_document
    # through a happy-path stub and assert the return shape says "ready"
    # and the doc isn't mutated to FAILED.
    # See test_worker_retry.py for the existing patching scaffold;
    # adapt it here. If the existing scaffold is too sparse, mark as
    # DONE_WITH_CONCERNS and propose a follow-up integration test
    # in test_blobstore_ingestion.py instead.
    pass  # Implementation depends on existing scaffold — see below
```

This test is best-effort. If the existing `test_worker_retry.py` scaffold doesn't allow easy injection of a `_safe_delete` mock, write the test directly in `apps/api/tests/integration/test_blobstore_ingestion.py` using the existing `_run_worker_task` helper, and skip the unit-level test. Document the choice in the commit message.

- [ ] **Step 5: Run tests** (`cd apps/api && uv run pytest tests/test_worker_retry.py tests/integration/test_blobstore_ingestion.py -v`).

- [ ] **Step 6: Lint** (`cd apps/api && uv run ruff check apps/api/src/worker.py && uv run ruff format --check apps/api/src/worker.py`).

- [ ] **Step 7: Commit** via `/commit` with message `fix(api): post-success exceptions never flip READY doc to FAILED (#79)`.

---

## Task 6: Harden `scripts/fly-secrets.sh`

**Files:**
- Modify: `scripts/fly-secrets.sh`

**Background:** Currently the script assumes CWD = repo root (hardcoded `apps/api/.env` path) and doesn't defend against accidental `bash -x` shell tracing leaking secrets to stderr.

- [ ] **Step 1: Update the script header**

At the top of `scripts/fly-secrets.sh`, after `#!/usr/bin/env bash`:

```bash
#!/usr/bin/env bash
# Sync secrets from local .env to both Fly apps.
# Usage: ./scripts/fly-secrets.sh [api|worker|both]
# Safe to invoke from any CWD.

set -euo pipefail
set +x  # defensive: refuse to leak secret values into stderr if a parent shell set -x

# Resolve repo root from script location so CWD doesn't matter.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

ENV_FILE="${REPO_ROOT}/apps/api/.env"
if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: ${ENV_FILE} not found" >&2
  exit 1
fi
```

Replace the existing `apps/api/.env not found` check + `source apps/api/.env` block with the absolute-path version above; keep the rest of the script intact.

- [ ] **Step 2: Smoke test from a different CWD**

```bash
cd /tmp && bash /Users/cristian-robertiosef/Desktop/Dev/mongo-rag/scripts/fly-secrets.sh --help 2>&1 | head -5 || echo "no --help, checking by other means"
cd /tmp && bash -n /Users/cristian-robertiosef/Desktop/Dev/mongo-rag/scripts/fly-secrets.sh && echo "syntax ok"
```

- [ ] **Step 3: Commit** via `/commit` with message `fix(infra): fly-secrets.sh works from any CWD + defends against set -x (#79)`.

---

## Task 7: `setup_supabase_storage.py` exits non-zero when lifecycle fails

**Files:**
- Modify: `scripts/setup_supabase_storage.py`
- Modify: `docs/deploy.md` (callout the manual fallback path)

**Background:** Currently the script prints a WARNING and returns 0 when `put_bucket_lifecycle_configuration` fails. CI / Terraform-style success gates won't notice that the 24-hour cleanup — the only mechanism preventing storage cost runaway from API crashes between `put` and `delay` — never landed.

- [ ] **Step 1: Update the lifecycle-config branch in `main()`**

```python
    try:
        client.put_bucket_lifecycle_configuration(
            Bucket=bucket, LifecycleConfiguration=rules
        )
        print(f"Lifecycle rule installed on {bucket!r} (delete after 1 day)")
    except ClientError as e:
        # Supabase Storage's S3-compat layer may not implement lifecycle ops.
        code = e.response.get("Error", {}).get("Code")
        print(
            f"WARNING: lifecycle config failed ({code}). "
            f"Configure the 1-day expiration manually via the Supabase dashboard "
            f"(Storage → {bucket} → Configuration). Bucket creation succeeded.",
            file=sys.stderr,
        )
        return 2  # distinct non-zero so CI / scripts can detect partial success
    return 0
```

- [ ] **Step 2: Update `docs/deploy.md`** — in the Supabase Storage setup section, add:

> **Note:** `setup_supabase_storage.py` exits 2 (not 0) when the lifecycle rule failed to install via the S3 API. This is non-fatal — the bucket exists and is usable — but you must configure the 1-day object expiration manually in the Supabase dashboard before going live, otherwise blob cost will accumulate.

- [ ] **Step 3: Lint** (`cd apps/api && uv run ruff check scripts/setup_supabase_storage.py && uv run ruff format --check scripts/setup_supabase_storage.py`).

- [ ] **Step 4: Commit** via `/commit` with message `fix(infra): setup_supabase_storage.py exits 2 when lifecycle fails (#79)`.

---

## Task 8: Drop redundant broad-except in delete paths

**Files:**
- Modify: `apps/api/src/services/blobstore/supabase.py` — `SupabaseBlobStore.delete`
- Modify: `apps/api/src/worker.py` — `_safe_delete`

**Background:** `SupabaseBlobStore.delete` swallows `ClientError` AND has a second bare `except Exception` swallowing everything else. `_safe_delete` then ALSO wraps in `except Exception`. Three layers of broad-swallow on the same call. If `_parse(uri)` raises `ValueError` (malformed URI leaked into a Supabase store call), the error is swallowed and nothing alerts.

- [ ] **Step 1: Tighten `SupabaseBlobStore.delete`**

In `apps/api/src/services/blobstore/supabase.py`, replace the current `delete` body with:

```python
    async def delete(self, uri: str) -> None:
        import asyncio

        bucket, key = self._parse(uri)  # let ValueError propagate — programming error
        try:
            await asyncio.to_thread(
                self._client.delete_object, Bucket=bucket, Key=key
            )
        except ClientError as e:
            # Idempotent + non-blocking — log and swallow. Lifecycle rule is the safety net.
            logger.warning("blob_delete_failed", extra={"uri": uri, "error": str(e)})
```

The `_parse` call is now outside the try; URI errors surface as `ValueError` to the caller (the worker's `_safe_delete` catches them).

- [ ] **Step 2: Tighten `_safe_delete` in `worker.py`**

```python
async def _safe_delete(blob_store, blob_uri: str) -> None:
    """Delete with logged-but-swallowed BlobStoreError. ValueError propagates."""
    from src.services.blobstore import BlobStoreError

    try:
        await blob_store.delete(blob_uri)
    except BlobStoreError as e:
        task_logger.warning("blob_delete_failed: uri=%s err=%s", blob_uri, e)
    # Programming errors (ValueError from URI parsing, AttributeError, etc.)
    # propagate — they indicate a bug, not a transient infra issue.
```

- [ ] **Step 3: Run unit tests** (`cd apps/api && uv run pytest tests/test_blobstore_supabase.py tests/test_blobstore_filesystem.py -v`).

- [ ] **Step 4: Lint** (`cd apps/api && uv run ruff check apps/api/src/services/blobstore/supabase.py apps/api/src/worker.py && uv run ruff format --check apps/api/src/services/blobstore/supabase.py apps/api/src/worker.py`).

- [ ] **Step 5: Commit** via `/commit` with message `fix(api): _safe_delete propagates programming errors (#79)`.

---

## Task 9: Single source of truth for worker `settings`

**Files:**
- Modify: `apps/api/src/worker.py` — drop module-level `settings = load_settings()`, call inline in `_run`
- Modify: `apps/api/tests/integration/test_blobstore_ingestion.py` — drop the `monkeypatch.setattr("src.worker.settings", ...)` patches; rely on env-var monkeypatching only

**Background:** Worker has `settings = load_settings()` at module level (line 10) used throughout, AND `get_blob_store()` reads `load_settings()` fresh inside `_run`. Two sources of truth that diverge if anyone later memoizes `load_settings()`. Tests patch the module-level `settings` AND env vars — the test passes for both reasons but breaks if either path is touched.

- [ ] **Step 1: Inline the settings access**

In `apps/api/src/worker.py`:

1. Keep the import `from src.core.settings import load_settings` at the top.
2. Delete the line `settings = load_settings()` near the top.
3. The Celery `Celery(broker=..., backend=...)` call needs `redis_url` at module-import time. Replace `broker=settings.redis_url` with `broker=load_settings().redis_url` and same for backend. (This call only runs once per process at import, so the cost is fine.)
4. Inside both `ingest_document._run` and `ingest_url._run`, at the top, add:

```python
        settings = load_settings()
```

Then every existing `settings.foo` reference inside `_run` resolves correctly.

- [ ] **Step 2: Verify no module-level `settings` references remain outside `_run`**

```bash
grep -n "^settings\.\|return settings\|settings = " apps/api/src/worker.py
```

Should show only the inline assignments inside the two `_run` functions.

- [ ] **Step 3: Update the integration test scaffold**

In `apps/api/tests/integration/test_blobstore_ingestion.py`, find the helper that does `monkeypatch.setattr("src.worker.settings", ...)`. Drop those lines. Verify the worker still picks up the patched `MONGODB_DATABASE` etc. via `load_settings()` reading env on each call. The `_reset_blob_store_cache` step is still required.

- [ ] **Step 4: Run integration test if `MONGODB_TEST_URI` is set**

```bash
cd apps/api && MONGODB_TEST_URI=$MONGODB_TEST_URI uv run pytest tests/integration/test_blobstore_ingestion.py -v -m integration
```

If `MONGODB_TEST_URI` is unset, the tests skip — that's expected and acceptable.

- [ ] **Step 5: Run unit tests to verify nothing else broke** (`cd apps/api && uv run pytest tests/ -m "not integration" -q`).

- [ ] **Step 6: Lint** (`cd apps/api && uv run ruff check apps/api/src/worker.py apps/api/tests/integration/test_blobstore_ingestion.py && uv run ruff format --check apps/api/src/worker.py apps/api/tests/integration/test_blobstore_ingestion.py`).

- [ ] **Step 7: Commit** via `/commit` with message `refactor(api): worker reads settings fresh inside _run, not module-level (#79)`.

---

## Final verification

- [ ] Run full unit test suite: `cd apps/api && uv run pytest -m "not integration" -q`. Expect 600+ pass, 1 pre-existing failure unrelated to #79 (`services/webhook_delivery.py:176` — pre-existing on `main`, separate issue).
- [ ] Run `cd apps/api && uv run ruff check apps/api && uv run ruff format --check apps/api`. Expect clean (or only the pre-existing format drift on files unrelated to #79: `auth/api_keys.py`, `routers/keys.py`, `tests/test_api_key_router.py`, `tests/test_api_keys_pg.py` — these are pre-existing on `main`).
- [ ] Run `cd apps/web && pnpm lint`. Expect clean.
- [ ] Optional: re-dispatch the adversarial reviewer to confirm Mediums + Lows are closed and nothing new emerged.
- [ ] `/ship` — push branch, open PR with `Closes #79`, body summarizes the original + followup commit set.

## Self-review summary

- **Spec coverage:** every item from the reviewer's Mediums + Lows is mapped to a task; no scope creep.
- **Type consistency:** `_emit_ingestion_complete` signature matches the spec's required field set; new `committed` flag is local to `_run`; `_safe_delete` signature unchanged.
- **Placeholder scan:** none — every step has executable code or a precise edit instruction.
- **Outstanding judgement calls:** Task 5's regression test depends on the existing test scaffold's flexibility; if it's too sparse, the test goes into `test_blobstore_ingestion.py` instead. Documented in step 4.
