# BlobStore Ingestion Handoff + Fly Deploy — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken `/tmp` filesystem handoff between FastAPI and the Celery worker with a `BlobStore` abstraction (URI-based, streamed, two backends), fix the silent ingestion-corruption bug, and ship the production deploy story (Vercel + Fly + Upstash + Supabase Storage). Local dev must remain offline.

**Architecture:** New `services/blobstore/` module exposes a `BlobStore` Protocol with `put` / `open` / `delete` / `signed_url`. Two impls: `FilesystemBlobStore` (`file://` URIs, used in dev/tests) and `SupabaseBlobStore` (`supabase://` URIs, S3-compatible boto3, used in prod). Router writes uploads via `BlobStore.put`, dispatches the URI to Celery, worker streams the URI back via `BlobStore.open`, runs Docling, deletes on success/terminal failure. Single Dockerfile switches between API and worker via `PROCESS_TYPE` env. Fly Machines runs both as separate process groups; Vercel runs `apps/web` with `vercel.ts`.

**Tech Stack:** FastAPI, Celery, MongoDB Atlas, Pydantic Settings, boto3 (S3-compatible), `storage3`, pytest, moto (S3 mocking), Docker, Fly Machines, Vercel.

**Spec:** `docs/superpowers/specs/2026-05-01-blobstore-fly-deploy-design.md`
**Issue:** [#79](https://github.com/cristian-robert/mongo-rag/issues/79)
**Branch:** `feat/79-blobstore-fly-deploy` (already created off `main`)

---

## Task 1: architect-agent IMPACT — surface map

**Files:** none (knowledge base call)

- [ ] **Step 1: Spawn architect-agent IMPACT**

Use the Agent tool with `subagent_type: "general-purpose"`, `model: "sonnet"`, prompt:

```
You are the architect-agent for the MongoRAG project. Read .claude/agents/architect-agent/AGENT.md
for your instructions. Then respond to this query:

IMPACT — adding services/blobstore/ module (Protocol + 2 impls), modifying
routers/ingest.py + worker.py + services/ingestion/ingest.py + core/settings.py,
new Dockerfile PROCESS_TYPE entrypoint switch, new fly.api.toml + fly.worker.toml,
shared volume in docker-compose, new env vars (BLOB_STORE, SUPABASE_STORAGE_BUCKET,
SUPABASE_S3_REGION; UPLOAD_TEMP_DIR semantic change). Bug B fix: remove silent
fallback in services/ingestion/ingest.py:238-242 — failures must raise.

Report: callers/consumers affected, env-var consumers, test files needing updates,
wiki articles needing updates, knowledge-base index entries that move.
```

- [ ] **Step 2: Capture the IMPACT response in commit notes**

The IMPACT report is reference material for later tasks. Save it inline in the next commit message body if it surfaces anything not already in the spec.

---

## Task 2: Settings additions

**Files:**
- Modify: `apps/api/src/core/settings.py`
- Modify: `apps/api/.env.example`
- Modify: `apps/api/tests/conftest.py` (add `BLOB_STORE` default)
- Test: `apps/api/tests/test_settings.py`

- [ ] **Step 1: Write failing test for new settings fields**

Append to `apps/api/tests/test_settings.py`:

```python
def test_blob_store_defaults_to_fs(monkeypatch):
    monkeypatch.delenv("BLOB_STORE", raising=False)
    from src.core.settings import Settings
    s = Settings()
    assert s.blob_store == "fs"
    assert s.supabase_storage_bucket is None
    assert s.supabase_s3_region == "us-east-1"


def test_blob_store_supabase_requires_bucket(monkeypatch):
    monkeypatch.setenv("BLOB_STORE", "supabase")
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "mongorag-uploads")
    from src.core.settings import Settings
    s = Settings()
    assert s.blob_store == "supabase"
    assert s.supabase_storage_bucket == "mongorag-uploads"
```

- [ ] **Step 2: Run tests and verify failure**

```bash
cd apps/api && uv run pytest tests/test_settings.py -k "blob_store" -v
```

Expected: FAIL — fields not defined.

- [ ] **Step 3: Add fields to `Settings` class**

In `apps/api/src/core/settings.py`, after the existing `upload_temp_dir` field (~line 213):

```python
    # Blob storage (ingestion handoff)
    blob_store: Literal["fs", "supabase"] = Field(
        default="fs",
        description="Backend for ingestion blob handoff: 'fs' (local) or 'supabase'.",
    )

    supabase_storage_bucket: Optional[str] = Field(
        default=None,
        description="Supabase Storage bucket name. Required when blob_store='supabase'.",
    )

    supabase_s3_region: str = Field(
        default="us-east-1",
        description="boto3 region label for the Supabase S3-compatible endpoint.",
    )
```

Change the default for `upload_temp_dir` to `"./.tmp/uploads"` (was `/tmp/mongorag-uploads`):

```python
    upload_temp_dir: str = Field(
        default="./.tmp/uploads",
        description="Temporary directory for FilesystemBlobStore (and the uploaded-file staging area).",
    )
```

- [ ] **Step 4: Update `.env.example`**

Append to `apps/api/.env.example`:

```
# Blob storage (ingestion handoff)
BLOB_STORE=fs
SUPABASE_STORAGE_BUCKET=
SUPABASE_S3_REGION=us-east-1
UPLOAD_TEMP_DIR=./.tmp/uploads
```

- [ ] **Step 5: Update test conftest with default**

In `apps/api/tests/conftest.py`, after the existing `os.environ.setdefault(...)` block (line ~10):

```python
os.environ.setdefault("BLOB_STORE", "fs")
```

- [ ] **Step 6: Run tests, verify pass + nothing else broke**

```bash
cd apps/api && uv run pytest tests/test_settings.py -v
```

Expected: PASS (new tests + all existing).

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/core/settings.py apps/api/.env.example apps/api/tests/conftest.py apps/api/tests/test_settings.py
```

Use `/commit` with message: `feat(api): add BLOB_STORE / SUPABASE_STORAGE_BUCKET settings (#79)`.

---

## Task 3: BlobStore Protocol + errors + filename sanitization

**Files:**
- Create: `apps/api/src/services/blobstore/__init__.py`
- Create: `apps/api/src/services/blobstore/base.py`
- Test: `apps/api/tests/test_blobstore_base.py`

- [ ] **Step 1: Write failing tests for sanitization + error hierarchy**

Create `apps/api/tests/test_blobstore_base.py`:

```python
"""Unit tests for BlobStore Protocol base helpers."""

import pytest

from src.services.blobstore.base import (
    BlobAccessError,
    BlobNotFoundError,
    BlobStoreError,
    sanitize_filename,
)


class TestSanitizeFilename:
    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            sanitize_filename("")

    def test_strips_path_traversal(self):
        assert sanitize_filename("../../etc/passwd") == "etcpasswd"

    def test_strips_directory_separators(self):
        assert sanitize_filename("foo/bar\\baz.pdf") == "foobarbaz.pdf"

    def test_normalizes_unicode(self):
        # NFKC: full-width letter A → A
        assert sanitize_filename("Ａ.pdf") == "A.pdf"

    def test_caps_length_at_255(self):
        long = "a" * 300 + ".pdf"
        assert len(sanitize_filename(long)) == 255

    def test_preserves_normal_filenames(self):
        assert sanitize_filename("cod_fiscal_norme_2023.md") == "cod_fiscal_norme_2023.md"

    def test_rejects_after_sanitization(self):
        with pytest.raises(ValueError):
            sanitize_filename("../")


class TestErrorHierarchy:
    def test_not_found_inherits_from_blob_store_error(self):
        assert issubclass(BlobNotFoundError, BlobStoreError)

    def test_access_inherits_from_blob_store_error(self):
        assert issubclass(BlobAccessError, BlobStoreError)
```

- [ ] **Step 2: Run, verify failure**

```bash
cd apps/api && uv run pytest tests/test_blobstore_base.py -v
```

Expected: FAIL — module does not exist.

- [ ] **Step 3: Create base module**

Create `apps/api/src/services/blobstore/__init__.py`:

```python
"""BlobStore — object-storage abstraction for ingestion handoff."""

from src.services.blobstore.base import (
    BlobAccessError,
    BlobNotFoundError,
    BlobStore,
    BlobStoreError,
    sanitize_filename,
)

__all__ = [
    "BlobStore",
    "BlobStoreError",
    "BlobNotFoundError",
    "BlobAccessError",
    "sanitize_filename",
]
```

Create `apps/api/src/services/blobstore/base.py`:

```python
"""BlobStore Protocol, errors, and shared helpers."""

from __future__ import annotations

import re
import unicodedata
from typing import (
    AsyncContextManager,
    AsyncIterator,
    BinaryIO,
    Protocol,
    runtime_checkable,
)

_MAX_FILENAME_LEN = 255
_PATH_TRAVERSAL = re.compile(r"[/\\.]+")


class BlobStoreError(Exception):
    """Base class for BlobStore failures."""


class BlobNotFoundError(BlobStoreError):
    """The requested blob does not exist. Terminal — do not retry."""


class BlobAccessError(BlobStoreError):
    """Transient failure (5xx, network, timeout). Retryable."""


def sanitize_filename(name: str) -> str:
    """Reject path traversal, normalize unicode, cap length at 255 chars.

    Raises:
        ValueError: if `name` is empty or sanitizes down to empty.
    """
    if not name:
        raise ValueError("filename is empty")
    normalized = unicodedata.normalize("NFKC", name)
    cleaned = normalized.replace("/", "").replace("\\", "")
    cleaned = cleaned.lstrip(".")  # remove leading dots (.., .hidden, etc.)
    if not cleaned:
        raise ValueError("filename is empty after sanitization")
    return cleaned[:_MAX_FILENAME_LEN]


@runtime_checkable
class BlobStore(Protocol):
    """Object-storage abstraction for ingestion handoff."""

    async def put(
        self,
        key: str,
        source: BinaryIO | AsyncIterator[bytes],
        content_type: str | None = None,
    ) -> str:
        """Stream `source` to `key`. Returns the URI (e.g. supabase://bucket/key, file:///abs)."""
        ...

    def open(self, uri: str) -> AsyncContextManager[AsyncIterator[bytes]]:
        """Stream bytes back. Raises BlobNotFoundError on 404, BlobAccessError on transient 5xx/network."""
        ...

    async def delete(self, uri: str) -> None:
        """Idempotent. Logs but never raises on Supabase errors — lifecycle rule is the safety net."""
        ...

    async def signed_url(self, uri: str, expires_in: int = 3600) -> str:
        """Declared in Protocol; not called by ingestion. Reserved for future dashboard download."""
        ...
```

Note on the `_PATH_TRAVERSAL` regex: the test `strips_path_traversal` asserts `../../etc/passwd → etcpasswd`. The implementation above achieves that via `replace("/", "")` then `lstrip(".")` — which is good enough and easier to reason about than a regex. The unused `_PATH_TRAVERSAL` constant is removed in the next step.

- [ ] **Step 4: Remove the unused regex constant**

Edit `apps/api/src/services/blobstore/base.py` to delete the `_PATH_TRAVERSAL = re.compile(...)` line and the `import re` line. The implementation only needs `unicodedata`.

- [ ] **Step 5: Run tests, verify pass**

```bash
cd apps/api && uv run pytest tests/test_blobstore_base.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/services/blobstore/__init__.py apps/api/src/services/blobstore/base.py apps/api/tests/test_blobstore_base.py
```

Use `/commit` with message: `feat(api): add BlobStore Protocol + errors + sanitize_filename (#79)`.

---

## Task 4: FilesystemBlobStore implementation

**Files:**
- Create: `apps/api/src/services/blobstore/filesystem.py`
- Test: `apps/api/tests/test_blobstore_filesystem.py`

- [ ] **Step 1: Write failing tests for round-trip + errors**

Create `apps/api/tests/test_blobstore_filesystem.py`:

```python
"""Unit tests for FilesystemBlobStore."""

import io

import pytest

from src.services.blobstore import BlobNotFoundError
from src.services.blobstore.filesystem import FilesystemBlobStore


@pytest.mark.asyncio
async def test_put_returns_file_uri(tmp_path):
    store = FilesystemBlobStore(root=str(tmp_path))
    uri = await store.put("tenant-a/doc-1/foo.txt", io.BytesIO(b"hello"), "text/plain")
    assert uri.startswith("file://")
    assert uri.endswith("/tenant-a/doc-1/foo.txt")


@pytest.mark.asyncio
async def test_round_trip_bytes(tmp_path):
    store = FilesystemBlobStore(root=str(tmp_path))
    payload = b"the quick brown fox" * 1000  # 19_000 bytes
    uri = await store.put("tenant-a/doc-1/data.bin", io.BytesIO(payload))
    chunks = bytearray()
    async with store.open(uri) as stream:
        async for chunk in stream:
            chunks.extend(chunk)
    assert bytes(chunks) == payload


@pytest.mark.asyncio
async def test_open_missing_raises_not_found(tmp_path):
    store = FilesystemBlobStore(root=str(tmp_path))
    with pytest.raises(BlobNotFoundError):
        async with store.open(f"file://{tmp_path}/nope.bin"):
            pass


@pytest.mark.asyncio
async def test_delete_is_idempotent(tmp_path):
    store = FilesystemBlobStore(root=str(tmp_path))
    uri = await store.put("tenant-a/doc-1/foo.txt", io.BytesIO(b"x"))
    await store.delete(uri)
    await store.delete(uri)  # second call must not raise


@pytest.mark.asyncio
async def test_put_creates_intermediate_dirs(tmp_path):
    store = FilesystemBlobStore(root=str(tmp_path))
    uri = await store.put("a/b/c/d/file.txt", io.BytesIO(b"x"))
    assert uri.startswith("file://")


@pytest.mark.asyncio
async def test_signed_url_returns_same_file_uri(tmp_path):
    """For local fs, signed_url is a no-op that returns the file:// URI as-is."""
    store = FilesystemBlobStore(root=str(tmp_path))
    uri = await store.put("a/file.txt", io.BytesIO(b"x"))
    signed = await store.signed_url(uri)
    assert signed == uri
```

- [ ] **Step 2: Run, verify failure**

```bash
cd apps/api && uv run pytest tests/test_blobstore_filesystem.py -v
```

Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement FilesystemBlobStore**

Create `apps/api/src/services/blobstore/filesystem.py`:

```python
"""FilesystemBlobStore — file:// backed BlobStore for tests and local dev."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, BinaryIO
from urllib.parse import urlparse

from src.services.blobstore.base import (
    BlobAccessError,
    BlobNotFoundError,
)

_CHUNK_SIZE = 64 * 1024  # 64 KiB


class FilesystemBlobStore:
    """Stores blobs on the local filesystem under `root`. URI scheme: file://."""

    def __init__(self, root: str) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    async def put(
        self,
        key: str,
        source,
        content_type: str | None = None,
    ) -> str:
        # Reject absolute keys and traversal.
        if key.startswith("/") or ".." in Path(key).parts:
            raise ValueError(f"unsafe key: {key}")
        target = self._root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as dst:
            if hasattr(source, "read"):
                while True:
                    chunk = source.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    dst.write(chunk)
            else:
                async for chunk in source:
                    dst.write(chunk)
        return f"file://{target}"

    @asynccontextmanager
    async def open(self, uri: str) -> AsyncIterator[AsyncIterator[bytes]]:
        path = self._path_from_uri(uri)
        if not path.exists():
            raise BlobNotFoundError(f"blob not found: {uri}")

        async def _stream() -> AsyncIterator[bytes]:
            try:
                with path.open("rb") as src:
                    while True:
                        chunk = src.read(_CHUNK_SIZE)
                        if not chunk:
                            break
                        yield chunk
            except OSError as e:
                raise BlobAccessError(f"read failed: {uri}") from e

        yield _stream()

    async def delete(self, uri: str) -> None:
        path = self._path_from_uri(uri)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            # Idempotent — never raise on cleanup.
            pass

    async def signed_url(self, uri: str, expires_in: int = 3600) -> str:
        # No-op for local fs. The URI is already directly usable by the worker.
        return uri

    def _path_from_uri(self, uri: str) -> Path:
        parsed = urlparse(uri)
        if parsed.scheme != "file":
            raise ValueError(f"not a file:// URI: {uri}")
        # urlparse for file:///abs/path puts the abs path in `path`.
        return Path(parsed.path)
```

- [ ] **Step 4: Run tests, verify pass**

```bash
cd apps/api && uv run pytest tests/test_blobstore_filesystem.py -v
```

Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/services/blobstore/filesystem.py apps/api/tests/test_blobstore_filesystem.py
```

Use `/commit` with message: `feat(api): FilesystemBlobStore (file:// URIs, streaming) (#79)`.

---

## Task 5: URI parsing + tenant assertion

**Files:**
- Create: `apps/api/src/services/blobstore/uri.py`
- Modify: `apps/api/src/services/blobstore/__init__.py`
- Test: `apps/api/tests/test_blobstore_uri.py`

- [ ] **Step 1: Write failing tests for tenant ownership check**

Create `apps/api/tests/test_blobstore_uri.py`:

```python
"""Tests for URI parsing and tenant ownership assertions."""

import pytest

from src.services.blobstore.uri import (
    InvalidBlobURIError,
    TenantOwnershipError,
    assert_tenant_owns_uri,
    extract_extension,
)


class TestAssertTenantOwnsURI:
    def test_supabase_uri_correct_tenant_passes(self):
        assert_tenant_owns_uri(
            "supabase://mongorag-uploads/tenant-a/doc-1/file.pdf",
            "tenant-a",
        )

    def test_supabase_uri_cross_tenant_rejected(self):
        with pytest.raises(TenantOwnershipError):
            assert_tenant_owns_uri(
                "supabase://mongorag-uploads/tenant-a/doc-1/file.pdf",
                "tenant-b",
            )

    def test_file_uri_correct_tenant_passes(self, tmp_path):
        uri = f"file://{tmp_path}/tenant-a/doc-1/file.pdf"
        assert_tenant_owns_uri(uri, "tenant-a", upload_root=str(tmp_path))

    def test_file_uri_cross_tenant_rejected(self, tmp_path):
        uri = f"file://{tmp_path}/tenant-a/doc-1/file.pdf"
        with pytest.raises(TenantOwnershipError):
            assert_tenant_owns_uri(uri, "tenant-b", upload_root=str(tmp_path))

    def test_unknown_scheme_rejected(self):
        with pytest.raises(InvalidBlobURIError):
            assert_tenant_owns_uri("s3://bucket/key", "tenant-a")

    def test_supabase_uri_missing_tenant_segment_rejected(self):
        with pytest.raises(InvalidBlobURIError):
            assert_tenant_owns_uri("supabase://mongorag-uploads/", "tenant-a")


class TestExtractExtension:
    def test_pdf(self):
        assert extract_extension("file:///x/y/file.pdf") == ".pdf"

    def test_no_extension(self):
        assert extract_extension("file:///x/y/file") == ""

    def test_supabase_uri(self):
        assert extract_extension("supabase://b/t/d/foo.docx") == ".docx"
```

- [ ] **Step 2: Run, verify failure**

```bash
cd apps/api && uv run pytest tests/test_blobstore_uri.py -v
```

Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement URI helpers**

Create `apps/api/src/services/blobstore/uri.py`:

```python
"""URI parsing and tenant ownership assertions for BlobStore URIs."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse


class InvalidBlobURIError(ValueError):
    """URI scheme/shape is not recognized."""


class TenantOwnershipError(PermissionError):
    """The tenant in the URI does not match the expected tenant_id."""


def assert_tenant_owns_uri(
    uri: str,
    tenant_id: str,
    upload_root: str | None = None,
) -> None:
    """Verify the URI's tenant prefix matches `tenant_id`.

    Args:
        uri: BlobStore URI (supabase://... or file://...).
        tenant_id: Expected tenant ID from the verified Principal.
        upload_root: For file:// URIs, the absolute path under which all blobs live.
            When None, falls back to settings.upload_temp_dir.

    Raises:
        InvalidBlobURIError: if the URI is not a recognized scheme/shape.
        TenantOwnershipError: if the tenant prefix does not match.
    """
    parsed = urlparse(uri)
    if parsed.scheme == "supabase":
        # supabase://<bucket>/<tenant>/<doc>/<file>
        # `netloc` is the bucket; `path` is /tenant/doc/file
        path_parts = parsed.path.lstrip("/").split("/", 1)
        if not path_parts or not path_parts[0]:
            raise InvalidBlobURIError(f"missing tenant segment: {uri}")
        if path_parts[0] != tenant_id:
            raise TenantOwnershipError(
                f"tenant mismatch: uri={path_parts[0]!r} expected={tenant_id!r}"
            )
        return

    if parsed.scheme == "file":
        if upload_root is None:
            from src.core.settings import load_settings

            upload_root = load_settings().upload_temp_dir
        root = Path(upload_root).resolve()
        target = Path(parsed.path).resolve()
        try:
            rel = target.relative_to(root)
        except ValueError as e:
            raise InvalidBlobURIError(f"file URI escapes upload_root: {uri}") from e
        if not rel.parts or rel.parts[0] != tenant_id:
            raise TenantOwnershipError(
                f"tenant mismatch: uri={rel.parts[0] if rel.parts else None!r} expected={tenant_id!r}"
            )
        return

    raise InvalidBlobURIError(f"unrecognized scheme: {parsed.scheme}")


def extract_extension(uri: str) -> str:
    """Return the file extension from the URI (lowercase, includes leading dot)."""
    parsed = urlparse(uri)
    return os.path.splitext(parsed.path)[1].lower()
```

- [ ] **Step 4: Re-export from package init**

Edit `apps/api/src/services/blobstore/__init__.py` — replace the entire file with:

```python
"""BlobStore — object-storage abstraction for ingestion handoff."""

from src.services.blobstore.base import (
    BlobAccessError,
    BlobNotFoundError,
    BlobStore,
    BlobStoreError,
    sanitize_filename,
)
from src.services.blobstore.uri import (
    InvalidBlobURIError,
    TenantOwnershipError,
    assert_tenant_owns_uri,
    extract_extension,
)

__all__ = [
    "BlobStore",
    "BlobStoreError",
    "BlobNotFoundError",
    "BlobAccessError",
    "InvalidBlobURIError",
    "TenantOwnershipError",
    "sanitize_filename",
    "assert_tenant_owns_uri",
    "extract_extension",
]
```

- [ ] **Step 5: Run tests, verify pass**

```bash
cd apps/api && uv run pytest tests/test_blobstore_uri.py -v
```

Expected: PASS (9 tests).

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/services/blobstore/uri.py apps/api/src/services/blobstore/__init__.py apps/api/tests/test_blobstore_uri.py
```

Use `/commit` with message: `feat(api): BlobStore URI parsing + tenant ownership assertion (#79)`.

---

## Task 6: Factory `get_blob_store()`

**Files:**
- Create: `apps/api/src/services/blobstore/factory.py`
- Modify: `apps/api/src/services/blobstore/__init__.py`
- Test: `apps/api/tests/test_blobstore_factory.py`

- [ ] **Step 1: Write failing tests**

Create `apps/api/tests/test_blobstore_factory.py`:

```python
"""Tests for BlobStore factory selection and fail-fast validation."""

import pytest

from src.services.blobstore.factory import get_blob_store, reset_blob_store_cache
from src.services.blobstore.filesystem import FilesystemBlobStore


@pytest.fixture(autouse=True)
def _reset_cache():
    reset_blob_store_cache()
    yield
    reset_blob_store_cache()


def test_returns_filesystem_when_blob_store_is_fs(monkeypatch, tmp_path):
    monkeypatch.setenv("BLOB_STORE", "fs")
    monkeypatch.setenv("UPLOAD_TEMP_DIR", str(tmp_path))
    store = get_blob_store()
    assert isinstance(store, FilesystemBlobStore)


def test_returns_singleton(monkeypatch, tmp_path):
    monkeypatch.setenv("BLOB_STORE", "fs")
    monkeypatch.setenv("UPLOAD_TEMP_DIR", str(tmp_path))
    assert get_blob_store() is get_blob_store()


def test_supabase_without_bucket_raises(monkeypatch):
    monkeypatch.setenv("BLOB_STORE", "supabase")
    monkeypatch.delenv("SUPABASE_STORAGE_BUCKET", raising=False)
    with pytest.raises(ValueError, match="SUPABASE_STORAGE_BUCKET"):
        get_blob_store()
```

- [ ] **Step 2: Run, verify failure**

```bash
cd apps/api && uv run pytest tests/test_blobstore_factory.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement factory**

Create `apps/api/src/services/blobstore/factory.py`:

```python
"""Factory for selecting BlobStore implementation by env."""

from __future__ import annotations

from src.core.settings import load_settings
from src.services.blobstore.base import BlobStore
from src.services.blobstore.filesystem import FilesystemBlobStore

_cached: BlobStore | None = None


def reset_blob_store_cache() -> None:
    """Test helper — clear the singleton cache."""
    global _cached
    _cached = None


def get_blob_store() -> BlobStore:
    """Return the configured BlobStore (process-local singleton)."""
    global _cached
    if _cached is not None:
        return _cached

    settings = load_settings()
    if settings.blob_store == "fs":
        _cached = FilesystemBlobStore(root=settings.upload_temp_dir)
    elif settings.blob_store == "supabase":
        if not settings.supabase_storage_bucket:
            raise ValueError(
                "SUPABASE_STORAGE_BUCKET is required when BLOB_STORE='supabase'"
            )
        if not settings.supabase_url:
            raise ValueError(
                "SUPABASE_URL is required when BLOB_STORE='supabase'"
            )
        # Import lazy — boto3 not needed in fs-only test runs.
        from src.services.blobstore.supabase import SupabaseBlobStore

        _cached = SupabaseBlobStore(
            bucket=settings.supabase_storage_bucket,
            supabase_url=settings.supabase_url,
            secret_key=_require_secret(settings),
            region=settings.supabase_s3_region,
        )
    else:
        raise ValueError(f"unknown BLOB_STORE: {settings.blob_store}")

    return _cached


def _require_secret(settings) -> str:
    # Supabase secret-key handling lives in core/postgres for DB; for storage
    # we read the same secret env. Importing here avoids a circular dep.
    import os

    secret = os.environ.get("SUPABASE_SECRET_KEY")
    if not secret:
        raise ValueError("SUPABASE_SECRET_KEY is required when BLOB_STORE='supabase'")
    return secret
```

- [ ] **Step 4: Re-export from package init**

Edit `apps/api/src/services/blobstore/__init__.py` to add:

```python
from src.services.blobstore.factory import get_blob_store, reset_blob_store_cache
```

And to its `__all__`:

```python
    "get_blob_store",
    "reset_blob_store_cache",
```

- [ ] **Step 5: Run tests, verify pass**

```bash
cd apps/api && uv run pytest tests/test_blobstore_factory.py -v
```

Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/services/blobstore/factory.py apps/api/src/services/blobstore/__init__.py apps/api/tests/test_blobstore_factory.py
```

Use `/commit` with message: `feat(api): BlobStore factory (BLOB_STORE env switch) (#79)`.

---

## Task 7: SupabaseBlobStore implementation

**Files:**
- Create: `apps/api/src/services/blobstore/supabase.py`
- Test: `apps/api/tests/test_blobstore_supabase.py`
- Modify: `apps/api/pyproject.toml` (add `boto3`, `moto[s3]` dev dep)

- [ ] **Step 1: Add dependencies**

```bash
cd apps/api && uv add boto3 && uv add --dev "moto[s3]"
```

- [ ] **Step 2: Write failing tests against `moto` mock S3**

Create `apps/api/tests/test_blobstore_supabase.py`:

```python
"""Unit tests for SupabaseBlobStore against a moto-mocked S3 endpoint."""

import io

import boto3
import pytest
from moto import mock_aws

from src.services.blobstore import BlobNotFoundError
from src.services.blobstore.supabase import SupabaseBlobStore


@pytest.fixture
def mock_s3():
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="mongorag-uploads")
        yield client


@pytest.fixture
def store(mock_s3):
    # SupabaseBlobStore configured to talk to the moto-mocked S3 in-process.
    return SupabaseBlobStore(
        bucket="mongorag-uploads",
        supabase_url="https://test.supabase.co",
        secret_key="test-secret",
        region="us-east-1",
        endpoint_url=None,  # moto intercepts the default boto3 endpoint
    )


@pytest.mark.asyncio
async def test_put_returns_supabase_uri(store):
    uri = await store.put("tenant-a/doc-1/foo.txt", io.BytesIO(b"hello"), "text/plain")
    assert uri == "supabase://mongorag-uploads/tenant-a/doc-1/foo.txt"


@pytest.mark.asyncio
async def test_round_trip(store):
    payload = b"x" * 100_000
    uri = await store.put("tenant-a/doc-1/blob.bin", io.BytesIO(payload))
    out = bytearray()
    async with store.open(uri) as stream:
        async for chunk in stream:
            out.extend(chunk)
    assert bytes(out) == payload


@pytest.mark.asyncio
async def test_open_missing_raises_not_found(store):
    with pytest.raises(BlobNotFoundError):
        async with store.open("supabase://mongorag-uploads/nope/key"):
            pass


@pytest.mark.asyncio
async def test_delete_idempotent(store):
    uri = await store.put("tenant-a/doc-1/foo.txt", io.BytesIO(b"x"))
    await store.delete(uri)
    await store.delete(uri)  # second call must not raise
```

- [ ] **Step 3: Run, verify failure**

```bash
cd apps/api && uv run pytest tests/test_blobstore_supabase.py -v
```

Expected: FAIL — module does not exist.

- [ ] **Step 4: Implement SupabaseBlobStore**

Create `apps/api/src/services/blobstore/supabase.py`:

```python
"""SupabaseBlobStore — S3-compatible BlobStore backed by Supabase Storage."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError

from src.services.blobstore.base import BlobAccessError, BlobNotFoundError

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 64 * 1024


class SupabaseBlobStore:
    """boto3 against the Supabase Storage S3-compatible endpoint. URI scheme: supabase://."""

    def __init__(
        self,
        bucket: str,
        supabase_url: str,
        secret_key: str,
        region: str = "us-east-1",
        endpoint_url: str | None | object = ...,  # sentinel: ... means "derive from supabase_url"
    ) -> None:
        self._bucket = bucket
        if endpoint_url is ...:
            endpoint_url = f"{supabase_url.rstrip('/')}/storage/v1/s3"
        kwargs = {
            "service_name": "s3",
            "region_name": region,
            "aws_access_key_id": secret_key,
            "aws_secret_access_key": secret_key,
        }
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url
        self._client = boto3.client(**kwargs)

    async def put(self, key: str, source, content_type: str | None = None) -> str:
        # boto3 upload_fileobj is sync but streams; run in threadpool for non-blocking.
        import asyncio

        if hasattr(source, "read"):
            extra = {"ContentType": content_type} if content_type else {}
            await asyncio.to_thread(
                self._client.upload_fileobj,
                source,
                self._bucket,
                key,
                ExtraArgs=extra,
            )
        else:
            # AsyncIterator → buffer to a SpooledTemporaryFile, then upload.
            import tempfile

            with tempfile.SpooledTemporaryFile(max_size=_CHUNK_SIZE * 16) as buf:
                async for chunk in source:
                    buf.write(chunk)
                buf.seek(0)
                extra = {"ContentType": content_type} if content_type else {}
                await asyncio.to_thread(
                    self._client.upload_fileobj,
                    buf,
                    self._bucket,
                    key,
                    ExtraArgs=extra,
                )
        return f"supabase://{self._bucket}/{key}"

    @asynccontextmanager
    async def open(self, uri: str) -> AsyncIterator[AsyncIterator[bytes]]:
        bucket, key = self._parse(uri)
        import asyncio

        try:
            obj = await asyncio.to_thread(
                self._client.get_object, Bucket=bucket, Key=key
            )
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            if code in ("NoSuchKey", "404"):
                raise BlobNotFoundError(f"blob not found: {uri}") from e
            raise BlobAccessError(f"s3 error: {code}") from e

        body = obj["Body"]

        async def _stream() -> AsyncIterator[bytes]:
            try:
                while True:
                    chunk = await asyncio.to_thread(body.read, _CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk
            finally:
                body.close()

        yield _stream()

    async def delete(self, uri: str) -> None:
        import asyncio

        try:
            bucket, key = self._parse(uri)
            await asyncio.to_thread(
                self._client.delete_object, Bucket=bucket, Key=key
            )
        except ClientError as e:
            # Idempotent + non-blocking — log and swallow. Lifecycle rule is the safety net.
            logger.warning("blob_delete_failed", extra={"uri": uri, "error": str(e)})
        except Exception as e:
            logger.warning("blob_delete_failed", extra={"uri": uri, "error": str(e)})

    async def signed_url(self, uri: str, expires_in: int = 3600) -> str:
        import asyncio

        bucket, key = self._parse(uri)
        url = await asyncio.to_thread(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        return url

    def _parse(self, uri: str) -> tuple[str, str]:
        parsed = urlparse(uri)
        if parsed.scheme != "supabase":
            raise ValueError(f"not a supabase:// URI: {uri}")
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
        return bucket, key
```

- [ ] **Step 5: Run tests, verify pass**

```bash
cd apps/api && uv run pytest tests/test_blobstore_supabase.py -v
```

Expected: PASS (4 tests). The `endpoint_url=None` in the test fixture lets moto intercept the default boto3 endpoint, validating the SDK contract without hitting Supabase.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/services/blobstore/supabase.py apps/api/tests/test_blobstore_supabase.py apps/api/pyproject.toml apps/api/uv.lock
```

Use `/commit` with message: `feat(api): SupabaseBlobStore (S3-compatible, streaming) (#79)`.

---

## Task 8: Bug B fix — fail loud in `services/ingestion/ingest.py`

**Files:**
- Modify: `apps/api/src/services/ingestion/ingest.py:238-242` (Docling fallback)
- Modify: `apps/api/src/services/ingestion/ingest.py:304-306` (audio fallback — same bug)
- Test: `apps/api/tests/test_ingestion_service.py` (regression test)

- [ ] **Step 1: Write failing regression tests**

Append to `apps/api/tests/test_ingestion_service.py`:

```python
def test_read_document_raises_on_missing_file(tmp_path):
    """Bug B regression — missing file MUST raise, not return a placeholder string."""
    from src.services.ingestion.ingest import DocumentIngestionPipeline, IngestionConfig

    pipeline = DocumentIngestionPipeline(
        config=IngestionConfig(),
        tenant_id="test-tenant",
        clean_before_ingest=False,
    )
    missing = str(tmp_path / "does-not-exist.pdf")
    with pytest.raises((FileNotFoundError, OSError)):
        pipeline.read_document(missing)


def test_read_document_never_returns_error_placeholder(tmp_path):
    """Bug B regression — content must never start with '[Error:' on any path."""
    from src.services.ingestion.ingest import DocumentIngestionPipeline, IngestionConfig

    pipeline = DocumentIngestionPipeline(
        config=IngestionConfig(),
        tenant_id="test-tenant",
        clean_before_ingest=False,
    )
    # A real markdown file should round-trip fine.
    p = tmp_path / "real.md"
    p.write_text("# Hello\n\nWorld")
    content, _ = pipeline.read_document(str(p))
    assert not content.startswith("[Error:")
```

(Ensure `import pytest` is present at the top of the file.)

- [ ] **Step 2: Run, verify the first test fails (current code returns placeholder)**

```bash
cd apps/api && uv run pytest tests/test_ingestion_service.py -k "raises_on_missing or never_returns_error" -v
```

Expected: FAIL (first test) — current code returns the placeholder string instead of raising.

- [ ] **Step 3: Replace silent fallback in Docling branch**

In `apps/api/src/services/ingestion/ingest.py`, change lines ~234–242 from:

```python
            except Exception as e:
                logger.error(f"Failed to convert {file_path} with Docling: {e}")
                # Fall back to raw text if Docling fails
                logger.warning(f"Falling back to raw text extraction for {file_path}")
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        return (f.read(), None)
                except Exception:
                    return (f"[Error: Could not read file {os.path.basename(file_path)}]", None)
```

to:

```python
            except Exception as e:
                logger.error(f"Failed to convert {file_path} with Docling: {e}")
                # Fall back to raw text if Docling fails — but only if the file actually exists.
                # Bug B: previously this swallowed FileNotFoundError and returned a placeholder
                # string that pollutes RAG retrieval. Failures must propagate.
                logger.warning(f"Falling back to raw text extraction for {file_path}")
                with open(file_path, "r", encoding="utf-8") as f:
                    return (f.read(), None)
```

- [ ] **Step 4: Replace silent fallback in audio branch**

In the same file, the `_transcribe_audio` method (~line 304–306) ends with:

```python
        except Exception as e:
            logger.error(f"Failed to transcribe {file_path} with Whisper ASR: {e}")
            return (f"[Error: Could not transcribe audio file {os.path.basename(file_path)}]", None)
```

Replace with:

```python
        except Exception as e:
            logger.error(f"Failed to transcribe {file_path} with Whisper ASR: {e}")
            # Bug B: never return a placeholder string — let the caller mark the document failed.
            raise
```

- [ ] **Step 5: Run regression tests, verify pass**

```bash
cd apps/api && uv run pytest tests/test_ingestion_service.py -k "raises_on_missing or never_returns_error" -v
```

Expected: PASS (2 tests).

- [ ] **Step 6: Run the full ingestion test file to catch any cascading breakage**

```bash
cd apps/api && uv run pytest tests/test_ingestion_service.py -v
```

Expected: PASS (or list of failures to fix — any existing test that *expected* the placeholder string is testing the bug, not the feature, and should be updated).

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/services/ingestion/ingest.py apps/api/tests/test_ingestion_service.py
```

Use `/commit` with message: `fix(api): remove silent placeholder fallback in read_document (#79)`.

---

## Task 9: Migrate `routers/ingest.py` — write to BlobStore

**Files:**
- Modify: `apps/api/src/routers/ingest.py:113-187` (file upload endpoint)
- Test: `apps/api/tests/test_ingest_router.py`

- [ ] **Step 1: Read existing tests to understand fixture shape**

```bash
cd apps/api && grep -n "ingest_document\|temp_path\|test_ingest" tests/test_ingest_router.py | head -30
```

Existing tests likely mock `ingest_document.delay` and assert on its call args. The new shape calls it with `blob_uri=...` instead of `temp_path=...`. Update fixtures accordingly.

- [ ] **Step 2: Update existing tests to expect the new signature**

In `apps/api/tests/test_ingest_router.py`, find the existing test that asserts on `ingest_document.delay` call args. Replace any `temp_path=` assertion with `blob_uri=` and assert it starts with `file://`.

Example (adapt to actual existing tests):

```python
def test_ingest_dispatches_with_blob_uri(client, mock_deps, monkeypatch, tmp_path):
    # Force fs blobstore rooted at tmp_path
    monkeypatch.setenv("BLOB_STORE", "fs")
    monkeypatch.setenv("UPLOAD_TEMP_DIR", str(tmp_path))
    from src.services.blobstore.factory import reset_blob_store_cache
    reset_blob_store_cache()

    captured = {}
    def fake_delay(**kwargs):
        captured.update(kwargs)
        class T: id = "task-123"
        return T()

    monkeypatch.setattr("src.routers.ingest.ingest_document.delay", fake_delay)

    response = client.post(
        "/api/v1/documents/ingest",
        headers=make_auth_header(),
        files={"file": ("test.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 202
    assert "blob_uri" in captured
    assert captured["blob_uri"].startswith("file://")
    assert "/test-tenant-001/" in captured["blob_uri"]
    assert "temp_path" not in captured  # old key is gone
```

- [ ] **Step 3: Run tests, verify failure**

```bash
cd apps/api && uv run pytest tests/test_ingest_router.py -v
```

Expected: FAIL — router still uses `temp_path`.

- [ ] **Step 4: Refactor `ingest_document_endpoint` (file upload)**

In `apps/api/src/routers/ingest.py`, replace lines ~113–187 (from filename sanitization through `task = ingest_document.delay(...)`) with:

```python
    # Sanitize filename — centralized helper rejects empty + traversal sequences.
    from src.services.blobstore import (
        BlobStoreError,
        get_blob_store,
        sanitize_filename,
    )

    raw_name = file.filename or f"upload-{uuid.uuid4()}{ext}"
    try:
        safe_name = sanitize_filename(raw_name)
    except ValueError:
        safe_name = f"upload-{uuid.uuid4()}{ext}"
    source = safe_name

    meta: dict = {}
    if metadata:
        try:
            meta = json.loads(metadata)
        except json.JSONDecodeError:
            raise HTTPException(status_code=422, detail="Invalid metadata JSON")
        if not isinstance(meta, dict):
            raise HTTPException(status_code=422, detail="Metadata must be a JSON object")

    service = IngestionService(
        documents_collection=deps.documents_collection,
        chunks_collection=deps.chunks_collection,
    )

    document_id = await service.create_pending_document(
        tenant_id=tenant_id,
        title=title or os.path.splitext(source)[0],
        source=source,
        metadata=meta,
    )

    blob_store = get_blob_store()
    key = f"{tenant_id}/{document_id}/{safe_name}"
    try:
        blob_uri = await blob_store.put(key, file.file, file.content_type)
    except BlobStoreError as e:
        await service.update_status(
            str(document_id), tenant_id, "failed", error_message="Upload failed"
        )
        logger.exception("Blob upload failed for doc=%s: %s", document_id, e)
        raise HTTPException(status_code=503, detail="Upload failed")

    try:
        task = ingest_document.delay(
            blob_uri=blob_uri,
            document_id=str(document_id),
            tenant_id=tenant_id,
            title=title or os.path.splitext(source)[0],
            source=source,
            metadata=meta,
        )
    except Exception:
        # Clean up blob and mark doc failed if Celery dispatch fails
        await blob_store.delete(blob_uri)
        await service.update_status(
            str(document_id), tenant_id, "failed", error_message="Task queue unavailable"
        )
        logger.exception("Failed to dispatch ingestion task for doc=%s", document_id)
        raise HTTPException(status_code=503, detail="Task queue unavailable")

    logger.info(
        "Ingestion dispatched: doc=%s, tenant=%s, task=%s, blob_uri=%s",
        document_id,
        tenant_id,
        task.id,
        blob_uri,
    )
```

Remove the now-dead imports `pathlib` and `shutil` from the top of the file (verify they aren't used elsewhere in the module first — `grep -n "pathlib\|shutil" apps/api/src/routers/ingest.py`).

- [ ] **Step 5: Run tests, verify pass**

```bash
cd apps/api && uv run pytest tests/test_ingest_router.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/routers/ingest.py apps/api/tests/test_ingest_router.py
```

Use `/commit` with message: `feat(api): router writes uploads via BlobStore.put (#79)`.

---

## Task 10: Migrate `worker.ingest_document` — read URI, delete on terminal

**Files:**
- Modify: `apps/api/src/worker.py:33-222` (ingest_document task)
- Test: existing `apps/api/tests/integration/test_ingestion_service_integration.py` (touch only if needed)

- [ ] **Step 1: Replace the task signature and body**

In `apps/api/src/worker.py`, replace the entire `ingest_document` task (lines 33–222) with:

```python
@celery_app.task(
    bind=True,
    name="mongorag.ingest_document",
    max_retries=3,
    autoretry_for=(ConnectionError, OSError),
    retry_backoff=10,
    retry_backoff_max=90,
)
def ingest_document(
    self,
    blob_uri: str,
    document_id: str,
    tenant_id: str,
    title: str,
    source: str,
    metadata: dict | None = None,
) -> dict:
    """Process a document through the ingestion pipeline.

    Reads the blob via the configured BlobStore, streams it to a tempfile,
    runs the existing pipeline, deletes the blob on success/terminal failure.

    Args:
        blob_uri: BlobStore URI (file://... or supabase://...). Must be tenant-prefixed.
        document_id: MongoDB document ID (created by the endpoint).
        tenant_id: Tenant ID for isolation; verified against the blob URI prefix.
        title: Document title.
        source: Original filename.
        metadata: Optional metadata dict.
    """
    import asyncio

    async def _run() -> dict:
        import os
        import tempfile

        from pymongo import AsyncMongoClient

        from src.models.document import DocumentModel, DocumentStatus
        from src.services.blobstore import (
            BlobAccessError,
            BlobNotFoundError,
            assert_tenant_owns_uri,
            extract_extension,
            get_blob_store,
        )
        from src.services.ingestion.chunker import ChunkingConfig, create_chunker
        from src.services.ingestion.embedder import create_embedder
        from src.services.ingestion.ingest import (
            DocumentIngestionPipeline,
            IngestionConfig,
        )
        from src.services.ingestion.service import IngestionService

        # Security boundary: verify tenant ownership BEFORE any read.
        assert_tenant_owns_uri(blob_uri, tenant_id)

        client = AsyncMongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
        db = client[settings.mongodb_database]

        service = IngestionService(
            documents_collection=db[settings.mongodb_collection_documents],
            chunks_collection=db[settings.mongodb_collection_chunks],
        )

        blob_store = get_blob_store()
        blob_size = 0
        blob_read_failed = False
        docling_failed = False
        tmp_path: str | None = None

        try:
            await service.update_status(document_id, tenant_id, DocumentStatus.PROCESSING)

            ext = extract_extension(blob_uri) or ".bin"

            # Stream blob → tempfile (Docling needs a real path).
            try:
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as dst:
                    tmp_path = dst.name
                    async with blob_store.open(blob_uri) as stream:
                        async for chunk in stream:
                            dst.write(chunk)
                            blob_size += len(chunk)
            except BlobNotFoundError as e:
                blob_read_failed = True
                await service.update_status(
                    document_id,
                    tenant_id,
                    DocumentStatus.FAILED,
                    error_message=f"blob_not_found: {e}",
                )
                # Terminal — delete the (already-missing) blob and surface as success-no-retry.
                await _safe_delete(blob_store, blob_uri)
                return {"document_id": document_id, "status": "failed", "chunk_count": 0}
            except BlobAccessError as e:
                blob_read_failed = True
                # Retryable — re-raise so Celery's autoretry kicks in.
                raise

            # Existing pipeline.
            config = IngestionConfig()
            pipeline = DocumentIngestionPipeline(
                config=config, tenant_id=tenant_id, clean_before_ingest=False
            )

            try:
                content, docling_doc = pipeline.read_document(tmp_path)
            except Exception:
                docling_failed = True
                raise

            if not content.strip():
                await service.update_status(
                    document_id,
                    tenant_id,
                    DocumentStatus.FAILED,
                    error_message="Document is empty or could not be parsed",
                )
                await _safe_delete(blob_store, blob_uri)
                return {"document_id": document_id, "status": "failed", "chunk_count": 0}

            content_hash = DocumentModel.hash_content(content)

            existing_doc = await service.check_duplicate(tenant_id, source, content_hash)
            if existing_doc:
                await service.update_status(
                    document_id,
                    tenant_id,
                    DocumentStatus.FAILED,
                    error_message="Duplicate of existing document",
                )
                await _safe_delete(blob_store, blob_uri)
                existing_id = str(existing_doc["_id"])
                existing_chunks = existing_doc.get("chunk_count", 0)
                task_logger.info(
                    "Duplicate detected for %s, reusing existing %s",
                    document_id,
                    existing_id,
                )
                return {
                    "document_id": existing_id,
                    "status": "ready",
                    "chunk_count": existing_chunks,
                }

            latest_version = await service.get_latest_version(tenant_id, source)
            version = latest_version + 1
            resolved_title = title if title else pipeline.extract_title(content, tmp_path)

            chunker = create_chunker(ChunkingConfig(max_tokens=config.max_tokens))
            chunks = await chunker.chunk_document(
                content=content,
                title=resolved_title,
                source=source,
                metadata=metadata or {},
                docling_doc=docling_doc,
            )

            if not chunks:
                await service.update_status(
                    document_id,
                    tenant_id,
                    DocumentStatus.FAILED,
                    error_message="No chunks created from document",
                )
                await _safe_delete(blob_store, blob_uri)
                return {"document_id": document_id, "status": "failed", "chunk_count": 0}

            embedder = create_embedder()
            embedded_chunks = await embedder.embed_chunks(chunks)

            chunk_count = await service.store_chunks(
                chunks=embedded_chunks,
                document_id=document_id,
                tenant_id=tenant_id,
                source=source,
                version=version,
                embedding_model=settings.embedding_model,
            )

            await service.update_status(
                document_id,
                tenant_id,
                DocumentStatus.READY,
                chunk_count=chunk_count,
                content_hash=content_hash,
                version=version,
                content=content,
            )

            # Success — delete blob (lifecycle rule is the safety net if this fails).
            await _safe_delete(blob_store, blob_uri)

            task_logger.info(
                "ingestion_complete",
                extra={
                    "document_id": document_id,
                    "tenant_id": tenant_id,
                    "blob_uri": blob_uri,
                    "blob_size_bytes": blob_size,
                    "status": "ready",
                    "chunks": chunk_count,
                    "blob_read_failed": False,
                    "docling_failed": False,
                },
            )

            return {
                "document_id": document_id,
                "status": "ready",
                "chunk_count": chunk_count,
            }

        except Exception as e:
            task_logger.exception("Ingestion failed: doc=%s, error=%s", document_id, str(e))
            safe_error = type(e).__name__
            if isinstance(e, (ValueError, TypeError, FileNotFoundError)):
                safe_error = f"{type(e).__name__}: {str(e)}"
            try:
                await service.update_status(
                    document_id,
                    tenant_id,
                    DocumentStatus.FAILED,
                    error_message=safe_error,
                )
            except Exception:
                task_logger.exception("Failed to update status after error")

            task_logger.info(
                "ingestion_complete",
                extra={
                    "document_id": document_id,
                    "tenant_id": tenant_id,
                    "blob_uri": blob_uri,
                    "blob_size_bytes": blob_size,
                    "status": "failed",
                    "chunks": 0,
                    "blob_read_failed": blob_read_failed,
                    "docling_failed": docling_failed,
                },
            )

            # Terminal-after-retries cleanup: if Celery is going to give up after this raise,
            # delete the blob. We can't tell from inside the task whether retries are exhausted,
            # so we delete on every retry-causing failure EXCEPT BlobAccessError (transient).
            if not isinstance(e, BlobAccessError):
                await _safe_delete(blob_store, blob_uri)

            raise

        finally:
            await client.close()
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    return asyncio.run(_run())


async def _safe_delete(blob_store, blob_uri: str) -> None:
    """Delete with logged-but-swallowed errors. Lifecycle rule is the safety net."""
    try:
        await blob_store.delete(blob_uri)
    except Exception as e:  # noqa: BLE001
        task_logger.warning("blob_delete_failed: uri=%s err=%s", blob_uri, e)
```

Note on retry-vs-terminal cleanup: the simpler model — "delete on every non-`BlobAccessError` exit, including retryable Docling failures" — would orphan the blob across retries. To keep the blob available for retries while still cleaning up on terminal failures, the right shape uses Celery's `on_failure` hook. The implementation above is the conservative variant; refine in the next step.

- [ ] **Step 2: Refine retry vs terminal cleanup**

Replace the cleanup lines in the `except Exception` block (`if not isinstance(e, BlobAccessError): await _safe_delete(...)`) with retry-aware handling. Add at the top of `worker.py`:

```python
def _is_terminal_failure(task, exc: Exception) -> bool:
    """Returns True if this is the last attempt (no more retries) or a non-retryable exc."""
    from src.services.blobstore import BlobNotFoundError, TenantOwnershipError

    if isinstance(exc, (BlobNotFoundError, TenantOwnershipError, ValueError, TypeError)):
        return True
    return task.request.retries >= task.max_retries
```

Then in the task's `except Exception` block, replace the cleanup line with:

```python
            if _is_terminal_failure(self, e):
                await _safe_delete(blob_store, blob_uri)
```

This deletes the blob on:
- explicit non-retryable errors (BlobNotFoundError, TenantOwnership, programming errors), and
- retries exhausted.

Otherwise it keeps the blob for the next retry.

- [ ] **Step 3: Update existing worker tests**

```bash
cd apps/api && grep -rn "temp_path\|ingest_document\.delay\|ingest_document(temp" tests/
```

For each test that calls `ingest_document(temp_path=...)`, change to `ingest_document(blob_uri=...)` with a `file://` URI created via the `FilesystemBlobStore` test fixture. If a worker integration test exists, ensure it writes the blob via `blob_store.put` first.

- [ ] **Step 4: Run unit tests**

```bash
cd apps/api && uv run pytest tests/test_ingest_router.py tests/test_ingestion_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/worker.py apps/api/tests/
```

Use `/commit` with message: `feat(api): worker streams blob URI, deletes on success/terminal (#79)`.

---

## Task 11: Migrate `worker.ingest_url` — write fetched bytes to BlobStore

**Files:**
- Modify: `apps/api/src/worker.py:225-462` (ingest_url task)
- Modify: `apps/api/src/routers/ingest.py:190-262` (URL endpoint — only the dispatch shape if needed)

**Decision:** The URL fetch happens *inside the worker* today, after dispatch. To unify on one read path, the cleanest move is: keep the worker fetching the URL, but write the fetched bytes through `BlobStore.put`, then proceed via the same code path as `ingest_document`. This preserves SSRF defense location.

- [ ] **Step 1: Refactor `ingest_url` to write fetched bytes through BlobStore**

In `apps/api/src/worker.py`, in the `ingest_url` task (line ~225), find the block that writes the fetched response to a tempfile (~lines 320–326):

```python
            ext = mime_to_ext.get(fetched.content_type, ".bin")
            temp_path = os.path.join(temp_dir, f"document{ext}")
            with open(temp_path, "wb") as f:
                f.write(fetched.content)
```

Replace with:

```python
            from src.services.blobstore import get_blob_store

            ext = mime_to_ext.get(fetched.content_type, ".bin")
            blob_store = get_blob_store()
            key = f"{tenant_id}/{document_id}/url-fetch{ext}"

            import io
            blob_uri = await blob_store.put(key, io.BytesIO(fetched.content), fetched.content_type)

            # Stream back to a tempfile in the worker — same hot path as ingest_document.
            temp_path = os.path.join(temp_dir, f"document{ext}")
            async with blob_store.open(blob_uri) as stream:
                with open(temp_path, "wb") as f:
                    async for chunk in stream:
                        f.write(chunk)
```

And in the `finally` block at the bottom of `_run`, add blob cleanup:

```python
        finally:
            await client.close()
            import shutil as _shutil

            if os.path.exists(temp_dir):
                _shutil.rmtree(temp_dir, ignore_errors=True)

            # Delete the blob copy of the fetched URL content.
            try:
                if "blob_uri" in dir() and "blob_store" in dir():
                    await blob_store.delete(blob_uri)
            except Exception:
                task_logger.warning("blob_delete_failed for url ingestion: %s", document_id)
```

Note: this is conservative — `blob_uri` may not exist if fetch failed before the BlobStore call. The `dir()` check guards against `NameError`. A cleaner alternative is to declare `blob_uri = None` at the top of `_run` and check `if blob_uri:` — refactor accordingly during code review.

- [ ] **Step 2: Run url ingest tests**

```bash
cd apps/api && uv run pytest tests/test_url_loader.py tests/test_ingest_router.py -v -k "url"
```

Expected: PASS. Adjust router tests if they assert on dispatch shape.

- [ ] **Step 3: Commit**

```bash
git add apps/api/src/worker.py
```

Use `/commit` with message: `feat(api): URL ingestion writes fetched bytes through BlobStore (#79)`.

---

## Task 12: Integration tests — full flow + missing blob + Bug B regression

**Files:**
- Create: `apps/api/tests/integration/test_blobstore_ingestion.py`

- [ ] **Step 1: Read the existing integration conftest**

```bash
cd apps/api && cat tests/integration/conftest.py | head -80
```

Note its fixtures (Mongo client, Celery, etc.) — this test file reuses them.

- [ ] **Step 2: Write integration tests**

Create `apps/api/tests/integration/test_blobstore_ingestion.py`:

```python
"""Integration tests for the BlobStore-backed ingestion pipeline.

These tests run against a real Mongo + real Celery worker (via docker-compose.dev.yml
or the project's existing integration harness).
"""

import io

import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_ingestion_happy_path_with_filesystem_blobstore(
    integration_client, mongo_db, tmp_path, monkeypatch
):
    """End-to-end: upload markdown → blob written → worker reads → chunks stored as `ready`."""
    monkeypatch.setenv("BLOB_STORE", "fs")
    monkeypatch.setenv("UPLOAD_TEMP_DIR", str(tmp_path))
    from src.services.blobstore.factory import reset_blob_store_cache
    reset_blob_store_cache()

    payload = b"# Test\n\nHello world. " + b"x " * 200
    response = integration_client.post(
        "/api/v1/documents/ingest",
        files={"file": ("test.md", payload, "text/markdown")},
        headers={"Authorization": "Bearer <integration-test-token>"},
    )
    assert response.status_code == 202
    document_id = response.json()["document_id"]

    # Wait for worker to complete (poll status endpoint up to 30s).
    import asyncio
    for _ in range(30):
        doc = await mongo_db["documents"].find_one({"_id": _to_object_id(document_id)})
        if doc and doc.get("status") in ("ready", "failed"):
            break
        await asyncio.sleep(1)

    assert doc["status"] == "ready"
    assert doc["chunk_count"] >= 1
    chunk = await mongo_db["chunks"].find_one({"document_id": _to_object_id(document_id)})
    assert chunk is not None
    assert not chunk["content"].startswith("[Error:")  # Bug B regression


@pytest.mark.asyncio
async def test_ingestion_missing_blob_marks_failed(
    integration_client, mongo_db, tmp_path, monkeypatch
):
    """If the blob is gone before the worker reads it, document ends `failed`."""
    monkeypatch.setenv("BLOB_STORE", "fs")
    monkeypatch.setenv("UPLOAD_TEMP_DIR", str(tmp_path))
    from src.services.blobstore.factory import reset_blob_store_cache
    reset_blob_store_cache()

    response = integration_client.post(
        "/api/v1/documents/ingest",
        files={"file": ("test.md", b"# Test", "text/markdown")},
        headers={"Authorization": "Bearer <integration-test-token>"},
    )
    document_id = response.json()["document_id"]

    # Race-delete the blob before the worker picks it up. In practice we'd
    # mock get_blob_store(); here we use the FS root knowledge.
    import shutil
    shutil.rmtree(tmp_path, ignore_errors=True)

    import asyncio
    for _ in range(30):
        doc = await mongo_db["documents"].find_one({"_id": _to_object_id(document_id)})
        if doc and doc.get("status") in ("ready", "failed"):
            break
        await asyncio.sleep(1)

    assert doc["status"] == "failed"
    assert doc["chunk_count"] == 0
    assert "blob_not_found" in (doc.get("error_message") or "").lower()


@pytest.mark.asyncio
async def test_chunks_never_contain_error_placeholder(mongo_db):
    """Bug B regression: scan the chunks collection for any `[Error:` content."""
    cursor = mongo_db["chunks"].find({"content": {"$regex": "^\\[Error:"}})
    leaked = await cursor.to_list(length=1)
    assert leaked == [], f"Found Bug B casualties: {leaked}"


def _to_object_id(s: str):
    from bson import ObjectId
    return ObjectId(s)
```

- [ ] **Step 3: Run integration tests**

```bash
cd apps/api && uv run pytest tests/integration/test_blobstore_ingestion.py -v -m integration
```

Expected: PASS, given the existing integration harness is up. If the harness needs a Celery worker, ensure `docker-compose.dev.yml` is running first.

- [ ] **Step 4: Commit**

```bash
git add apps/api/tests/integration/test_blobstore_ingestion.py
```

Use `/commit` with message: `test(api): integration tests for BlobStore ingestion + Bug B regression (#79)`.

---

## Task 13: Dockerfile + entrypoint switch

**Files:**
- Create: `scripts/entrypoint.sh`
- Modify: `apps/api/Dockerfile`
- Modify: `apps/api/.dockerignore` (no change unless `.tmp/` pattern absent)

- [ ] **Step 1: Create entrypoint script**

Create `scripts/entrypoint.sh`:

```bash
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
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/entrypoint.sh
```

- [ ] **Step 3: Read existing Dockerfile**

```bash
cat apps/api/Dockerfile | head -80
```

Identify where the current `CMD` / `ENTRYPOINT` lives.

- [ ] **Step 4: Update Dockerfile to use the entrypoint**

In `apps/api/Dockerfile`, replace the existing `CMD` (typically `CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8100"]`) with:

```dockerfile
ENV PROCESS_TYPE=api
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["tini", "--", "/entrypoint.sh"]
```

Verify the existing `tini` install line is still present; if not, add `RUN apt-get update && apt-get install -y --no-install-recommends tini && rm -rf /var/lib/apt/lists/*` to the runtime stage.

- [ ] **Step 5: Smoke test the build**

```bash
docker build -f apps/api/Dockerfile -t mongorag-api-test .
docker run --rm -e PROCESS_TYPE=invalid mongorag-api-test || true  # should print error and exit 1
```

Expected: error-and-exit-1 on the second command.

- [ ] **Step 6: Commit**

```bash
git add scripts/entrypoint.sh apps/api/Dockerfile
```

Use `/commit` with message: `feat(infra): single Dockerfile + PROCESS_TYPE entrypoint switch (#79)`.

---

## Task 14: Fly toml + secrets script + Supabase Storage setup script

**Files:**
- Create: `fly.api.toml`
- Create: `fly.worker.toml`
- Create: `scripts/fly-secrets.sh`
- Create: `scripts/setup_supabase_storage.py`

- [ ] **Step 1: Create `fly.api.toml`**

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
  processes = ["app"]

[[vm]]
  cpu_kind = "shared"
  cpus = 1
  memory_mb = 512
```

- [ ] **Step 2: Create `fly.worker.toml`**

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

- [ ] **Step 3: Create `scripts/fly-secrets.sh`**

```bash
#!/usr/bin/env bash
# Sync secrets from local .env to both Fly apps.
# Usage: ./scripts/fly-secrets.sh [api|worker|both]

set -euo pipefail

TARGET="${1:-both}"

SECRETS=(
  MONGODB_URI
  DATABASE_URL
  SUPABASE_URL
  SUPABASE_SECRET_KEY
  SUPABASE_JWT_SECRET
  SUPABASE_STORAGE_BUCKET
  LLM_API_KEY
  EMBEDDING_API_KEY
  STRIPE_SECRET_KEY
  STRIPE_WEBHOOK_SECRET
  REDIS_URL
  BLOB_STORE
  NEXTAUTH_SECRET
)

if [[ ! -f apps/api/.env ]]; then
  echo "ERROR: apps/api/.env not found" >&2
  exit 1
fi

# Load .env into the shell.
set -a
# shellcheck disable=SC1091
source apps/api/.env
set +a

set_for() {
  local app="$1"
  local args=()
  for k in "${SECRETS[@]}"; do
    if [[ -n "${!k:-}" ]]; then
      args+=("${k}=${!k}")
    fi
  done
  if [[ ${#args[@]} -eq 0 ]]; then
    echo "No secrets to set for ${app}"
    return
  fi
  echo "Setting ${#args[@]} secrets on ${app}..."
  fly secrets set --app "${app}" "${args[@]}"
}

case "${TARGET}" in
  api)    set_for mongorag-api ;;
  worker) set_for mongorag-worker ;;
  both)   set_for mongorag-api && set_for mongorag-worker ;;
  *)      echo "Usage: $0 [api|worker|both]" >&2; exit 1 ;;
esac
```

```bash
chmod +x scripts/fly-secrets.sh
```

- [ ] **Step 4: Create Supabase Storage setup script**

Create `scripts/setup_supabase_storage.py`:

```python
"""Bootstrap the Supabase Storage bucket used by SupabaseBlobStore.

Idempotent — safe to run multiple times. Run once per environment after deploying.

Usage:
    BLOB_STORE=supabase \\
    SUPABASE_URL=https://<ref>.supabase.co \\
    SUPABASE_SECRET_KEY=... \\
    SUPABASE_STORAGE_BUCKET=mongorag-uploads \\
    uv run python scripts/setup_supabase_storage.py
"""

from __future__ import annotations

import os
import sys

import boto3
from botocore.exceptions import ClientError


def main() -> int:
    bucket = os.environ.get("SUPABASE_STORAGE_BUCKET")
    supabase_url = os.environ.get("SUPABASE_URL")
    secret_key = os.environ.get("SUPABASE_SECRET_KEY")

    if not (bucket and supabase_url and secret_key):
        print("ERROR: SUPABASE_STORAGE_BUCKET, SUPABASE_URL, SUPABASE_SECRET_KEY required")
        return 1

    endpoint = f"{supabase_url.rstrip('/')}/storage/v1/s3"
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=secret_key,
        aws_secret_access_key=secret_key,
        region_name="us-east-1",
    )

    # Create bucket if missing.
    try:
        client.head_bucket(Bucket=bucket)
        print(f"Bucket {bucket!r} already exists")
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code in ("404", "NoSuchBucket", "NotFound"):
            client.create_bucket(Bucket=bucket)
            print(f"Created bucket {bucket!r}")
        else:
            raise

    # 24h expiration lifecycle rule.
    rules = {
        "Rules": [
            {
                "ID": "delete-stale-uploads",
                "Status": "Enabled",
                "Filter": {"Prefix": ""},
                "Expiration": {"Days": 1},
            }
        ]
    }
    client.put_bucket_lifecycle_configuration(
        Bucket=bucket, LifecycleConfiguration=rules
    )
    print(f"Lifecycle rule installed on {bucket!r} (delete after 1 day)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Note: Supabase Storage's S3 endpoint may not implement `put_bucket_lifecycle_configuration` — if that turns out to be the case, fall back to documenting the lifecycle rule as a Supabase dashboard config step in `docs/deploy.md` and remove the lifecycle call from this script.

- [ ] **Step 5: Commit**

```bash
git add fly.api.toml fly.worker.toml scripts/fly-secrets.sh scripts/setup_supabase_storage.py
```

Use `/commit` with message: `feat(infra): fly.toml + fly-secrets.sh + Supabase Storage bootstrap (#79)`.

---

## Task 15: Local dev wiring — compose + scripts/dev.sh + .gitignore + Vercel + CSP

**Files:**
- Modify: `docker-compose.dev.yml`
- Modify: `docker-compose.yml`
- Modify: `scripts/dev.sh`
- Modify: `.gitignore`
- Create: `apps/web/vercel.ts`
- Modify: `apps/web/next.config.ts` (CSP `connect-src` allowlist)

- [ ] **Step 1: Read current compose files**

```bash
cat docker-compose.dev.yml
echo "---"
cat docker-compose.yml
```

Identify the worker service and existing volume config.

- [ ] **Step 2: Update `docker-compose.dev.yml` worker service**

Find the `worker:` service and add to its `environment:` block:

```yaml
      BLOB_STORE: fs
      UPLOAD_TEMP_DIR: /workspace/.tmp/uploads
```

Add to its `volumes:` block (or create one if absent):

```yaml
    volumes:
      - ./.tmp/uploads:/workspace/.tmp/uploads:rw
```

- [ ] **Step 3: Update `docker-compose.yml` (full Docker dev) for shared named volume**

In the `services:` section, add to both `api:` and `worker:`:

```yaml
    volumes:
      - uploads:/workspace/.tmp/uploads
    environment:
      BLOB_STORE: fs
      UPLOAD_TEMP_DIR: /workspace/.tmp/uploads
```

At the bottom of the file, add:

```yaml
volumes:
  uploads:
```

(Merge into the existing `volumes:` block if one already exists.)

- [ ] **Step 4: Update `scripts/dev.sh`**

Read first:

```bash
cat scripts/dev.sh
```

Near the top (after the shebang and any existing env-loading block), add:

```bash
# --- BlobStore wiring ---
export BLOB_STORE="${BLOB_STORE:-fs}"
export UPLOAD_TEMP_DIR="${UPLOAD_TEMP_DIR:-$PWD/.tmp/uploads}"
mkdir -p "$UPLOAD_TEMP_DIR"

echo "BLOB_STORE=${BLOB_STORE}"

if [[ "${BLOB_STORE}" == "supabase" ]]; then
  : "${SUPABASE_STORAGE_BUCKET:?SUPABASE_STORAGE_BUCKET required when BLOB_STORE=supabase}"
  : "${SUPABASE_SECRET_KEY:?SUPABASE_SECRET_KEY required when BLOB_STORE=supabase}"
  : "${SUPABASE_URL:?SUPABASE_URL required when BLOB_STORE=supabase}"
fi
```

- [ ] **Step 5: Update `.gitignore`**

Append:

```
# BlobStore local-dev uploads
.tmp/
```

- [ ] **Step 6: Create `apps/web/vercel.ts`**

```typescript
import { type VercelConfig } from '@vercel/config/v1';

export const config: VercelConfig = {
  framework: 'nextjs',
  buildCommand: 'pnpm build',
  installCommand: 'pnpm install',
};
```

- [ ] **Step 7: Update CSP in `apps/web/next.config.ts`**

Read first:

```bash
grep -n "connect-src\|FastAPI\|API_URL" apps/web/next.config.ts | head -10
```

In the `connect-src` directive of the CSP, add the production Fly API hostname alongside the existing entries:

```typescript
// Existing: connect-src 'self' https://*.supabase.co ${env.NEXT_PUBLIC_API_URL ?? ''}
// Adjust to:
connect-src 'self' https://*.supabase.co https://mongorag-api.fly.dev ${env.NEXT_PUBLIC_API_URL ?? ''}
```

(Match exact existing syntax — the precise concatenation/template style varies. The semantic change is: ensure `https://mongorag-api.fly.dev` is in the `connect-src` allowlist.)

- [ ] **Step 8: Smoke test local dev**

```bash
./scripts/dev.sh
```

Expect: prints `BLOB_STORE=fs`, creates `.tmp/uploads/`. Stop after confirmation.

- [ ] **Step 9: Commit**

```bash
git add docker-compose.dev.yml docker-compose.yml scripts/dev.sh .gitignore apps/web/vercel.ts apps/web/next.config.ts
```

Use `/commit` with message: `feat(infra): local-dev BlobStore wiring + Vercel + CSP (#79)`.

---

## Task 16: Documentation — deploy.md, wiki articles, KB rebuild, architect index

**Files:**
- Create: `docs/deploy.md`
- Create: `.obsidian/wiki/decision-blobstore-handoff.md`
- Create: `.obsidian/wiki/decision-deploy-fly-vercel.md`
- Modify: `.obsidian/wiki/concept-celery-ingestion-worker.md`
- Modify: `.obsidian/wiki/feature-document-ingestion.md`
- Modify: `.obsidian/wiki/_index.md` (add new articles)
- Modify: `.obsidian/wiki/_tags.md` (add new tags)
- Modify: `docs/architecture.md`
- Modify: `.claude/agents/architect-agent/index.md`

- [ ] **Step 1: Write `docs/deploy.md`**

Create with sections: Overview, Stack components (Vercel/Fly/Upstash/Supabase Storage), First-time setup, Secrets, Smoke test, Rollback, Cost table. Use the spec's deploy section as the source. ~150 lines.

- [ ] **Step 2: Write `.obsidian/wiki/decision-blobstore-handoff.md`**

Use the template at `.claude/references/kb-article-template.md`. Frontmatter:

```yaml
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
```

Body covers: the problem (filesystem-split bugs A/B), the BlobStore Protocol shape, URI scheme decision, streaming choice, delete semantics, why we picked them.

- [ ] **Step 3: Write `.obsidian/wiki/decision-deploy-fly-vercel.md`**

Frontmatter:

```yaml
---
title: "Decision: Vercel + Fly + Upstash + Supabase Storage deploy"
type: decision
tags: [decision, deploy, infrastructure, fly, vercel, upstash]
created: 2026-05-01
updated: 2026-05-01
related:
  - "[[decision-blobstore-handoff]]"
status: compiled
---
```

Body covers: stack rationale (why Fly over Render/Railway, why Vercel for web, why Upstash for Redis, idle-cost analysis from the spec).

- [ ] **Step 4: Update `concept-celery-ingestion-worker.md`**

Add a section: "Handoff via BlobStore (post-#79)". Note the URI-based handoff. Add `[[decision-blobstore-handoff]]` to the related links.

- [ ] **Step 5: Update `feature-document-ingestion.md`**

Update the "Pipeline" section to reference the BlobStore step. Add `[[decision-blobstore-handoff]]` to related.

- [ ] **Step 6: Update `_index.md` and `_tags.md`**

Add `decision-blobstore-handoff.md` and `decision-deploy-fly-vercel.md` to the Decisions section of `_index.md`. Add any new tags (`blobstore`, `deploy`, `fly`, `vercel`, `upstash`) to `_tags.md`.

- [ ] **Step 7: Update `docs/architecture.md`**

In the Ingestion section, replace the "FastAPI writes to /tmp, Celery reads from /tmp" description with the BlobStore-based handoff. Add the diagram from the spec.

- [ ] **Step 8: Update `.claude/agents/architect-agent/index.md`**

Add `services/blobstore/` to the Backend Layout section under Core. Update Key Decisions to include `[[decision-blobstore-handoff]]` and `[[decision-deploy-fly-vercel]]`.

- [ ] **Step 9: Rebuild KB indexes**

```bash
KB_PATH=.obsidian node cli/kb-search.js index
```

Verify both `_search/index.json` and `_search/lean-index.json` are updated:

```bash
git status .obsidian/_search/
```

- [ ] **Step 10: Spawn architect-agent RECORD**

Use the Agent tool with `subagent_type: "general-purpose"`, `model: "sonnet"`, prompt:

```
You are the architect-agent for the MongoRAG project. Read .claude/agents/architect-agent/AGENT.md.
Then process this query:

RECORD domain:ingestion

Changes:
- Added services/blobstore/ module (Protocol + FilesystemBlobStore + SupabaseBlobStore + factory + URI helpers).
- routers/ingest.py and worker.py migrated from /tmp path-strings to BlobStore URIs.
- Bug B fix in services/ingestion/ingest.py: removed silent placeholder fallback in Docling and audio paths.
- Settings: BLOB_STORE, SUPABASE_STORAGE_BUCKET, SUPABASE_S3_REGION; UPLOAD_TEMP_DIR default changed.
- Single Dockerfile with PROCESS_TYPE entrypoint; new fly.api.toml + fly.worker.toml; scripts/fly-secrets.sh and scripts/setup_supabase_storage.py.
- Vercel apps/web/vercel.ts; CSP updated for mongorag-api.fly.dev.
- New wiki: decision-blobstore-handoff.md, decision-deploy-fly-vercel.md.
- Updated wiki: concept-celery-ingestion-worker, feature-document-ingestion.

Update .claude/agents/architect-agent/index.md and decisions/log.md accordingly.
```

- [ ] **Step 11: Commit**

```bash
git add docs/deploy.md docs/architecture.md .obsidian/wiki/ .obsidian/_search/ .claude/agents/architect-agent/
```

Use `/commit` with message: `docs(api): deploy guide + wiki articles + architect-agent RECORD (#79)`.

---

## Task 17: Final verification + ship

**Files:** none (verification commands)

- [ ] **Step 1: Run all unit tests**

```bash
cd apps/api && uv run pytest -m "not integration" -v
```

Expected: PASS.

- [ ] **Step 2: Run integration tests against running compose**

```bash
docker-compose -f docker-compose.dev.yml up -d
cd apps/api && uv run pytest -m integration -v
docker-compose -f docker-compose.dev.yml down
```

Expected: PASS.

- [ ] **Step 3: Run linters**

```bash
cd apps/api && uv run ruff check . && uv run ruff format --check .
cd apps/web && pnpm lint
```

Expected: clean.

- [ ] **Step 4: Manual smoke test — full ingestion locally**

```bash
./scripts/dev.sh &
DEV_PID=$!
sleep 10  # wait for API + worker
# Upload a real PDF via curl (use a test API key for the local test tenant)
curl -X POST http://localhost:8100/api/v1/documents/ingest \
  -H "Authorization: Bearer mrag_test_key" \
  -F "file=@data/sources/cod_fiscal_norme_2023.md"
# Poll /api/v1/documents/<id>/status until status=ready
# Verify the chunk count > 1 and no chunk content starts with "[Error:"
kill $DEV_PID
```

Expected: status=ready, chunk_count>1, content is real markdown not "[Error:".

- [ ] **Step 5: Run `/validate` (Superpowers Phase 2.5/5)**

Per project workflow. Validates the security checklist (tenant isolation enforced, SSRF intact, no secrets committed) and dispatches the Superpowers code-reviewer.

- [ ] **Step 6: Ship via `/ship`**

The `/ship` command opens the PR with `Closes #79`, runs Codex adversarial review (optional Step 1.6), and pushes via `/commit-push-pr`.

---

## Self-review summary

- **Spec coverage:** every locked decision (Approach C, scheme://bucket/key URIs, streaming both ends, app-level delete + lifecycle) is implemented. Bug A (Task 9–10) and Bug B (Task 8) both have regression tests. Fly + Vercel deploy artifacts (Task 13–15). Documentation + KB (Task 16). Verification + ship (Task 17).
- **Type consistency:** `BlobStore.put` accepts `BinaryIO | AsyncIterator[bytes]` everywhere; `BlobStore.open` returns `AsyncContextManager[AsyncIterator[bytes]]` everywhere; URI naming `blob_uri` in router and worker; tenant assertion helper named `assert_tenant_owns_uri` in all references.
- **Placeholder scan:** none. Every step has executable code or a precise edit instruction with the actual content to write.
- **Outstanding judgement calls flagged inline:** (a) Task 11's "if blob_uri" guard in URL ingestion (cleaner refactor noted), (b) Task 14's Supabase lifecycle rule may need to be configured via dashboard if the S3-compat layer doesn't accept it. Both are flagged with the remediation path.
