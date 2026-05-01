"""Integration tests for the BlobStore-backed ingestion pipeline.

These tests exercise the worker's ingestion task body directly (bypassing
Celery dispatch and the FastAPI HTTP layer) because the existing integration
harness only provides ``mongo_db``. They cover:

1. **Happy path** — a real markdown payload flows through the
   FilesystemBlobStore → worker reads → chunks land in Mongo. Asserts no chunk
   leaks the ``[Error:`` placeholder string (Bug B regression).
2. **Missing blob** — the blob is deleted before the worker runs. Document
   ends ``status=failed``, ``error_message`` contains ``blob_not_found``
   (Bug A regression: no silent placeholder corruption).
3. **Regression scan** — a pure DB scan asserting no chunk in the test DB
   contains content starting with ``[Error:`` (Bug B regression).

The happy-path test additionally requires a working OpenAI embedding API
because the worker invokes the real embedder; it will fail with a clear
embedding-related error if ``EMBEDDING_API_KEY`` is not valid.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


async def _seed_pending_document(mongo_db, tenant_id: str, source: str, title: str) -> str:
    """Create a pending document record and return its ID as a string.

    Bypasses the FastAPI endpoint (which the integration harness can't wire
    against ``mongo_db``) but uses the real ``IngestionService`` so the
    document shape matches what the worker expects.
    """
    from src.services.ingestion.service import IngestionService

    service = IngestionService(
        documents_collection=mongo_db["documents"],
        chunks_collection=mongo_db["chunks"],
    )
    return str(
        await service.create_pending_document(
            tenant_id=tenant_id, title=title, source=source, metadata={}
        )
    )


def _patch_worker_for_test_db(monkeypatch, mongo_db, tmp_path: Path) -> None:
    """Route the worker at the per-test Mongo DB and tmp blob root via env vars.

    The worker reads ``settings = load_settings()`` fresh inside each task's
    ``_run`` body, so monkeypatching the env vars here is sufficient — no
    need to patch a module-level ``settings`` attribute. The blob store
    factory cache is the only stateful seam left to reset.
    """
    import os

    from src.services.blobstore.factory import reset_blob_store_cache

    monkeypatch.setenv("BLOB_STORE", "fs")
    monkeypatch.setenv("UPLOAD_TEMP_DIR", str(tmp_path))
    monkeypatch.setenv("MONGODB_DATABASE", mongo_db.name)
    monkeypatch.setenv(
        "MONGODB_URI",
        os.environ.get("MONGODB_TEST_URI", os.environ["MONGODB_URI"]),
    )
    reset_blob_store_cache()


def _run_worker_task(blob_uri: str, document_id: str, tenant_id: str, source: str, title: str):
    """Invoke the worker's ingestion task body synchronously via Celery's apply().

    ``apply()`` runs the task locally with a real Celery ``self`` bound, so
    ``self.request.retries`` and the ``_is_terminal_failure`` cleanup paths
    behave the same as in production. ``throw=False`` means failures are
    captured in the result instead of re-raised, which we want — the worker
    updates the document status before raising, and the test asserts on that
    status, not on the raised exception.
    """
    from src.worker import ingest_document

    return ingest_document.apply(
        kwargs={
            "blob_uri": blob_uri,
            "document_id": document_id,
            "tenant_id": tenant_id,
            "title": title,
            "source": source,
            "metadata": {},
        },
        throw=False,
    )


async def test_ingestion_happy_path_with_filesystem_blobstore(
    mongo_db, tmp_path, monkeypatch
) -> None:
    """End-to-end: blob upload → worker → chunks in Mongo, no `[Error:` leak."""
    pytest.importorskip("docling")  # heavyweight optional dep

    _patch_worker_for_test_db(monkeypatch, mongo_db, tmp_path)

    tenant_id = "tenant-it-happy"
    source = "test.md"
    title = "Test"

    document_id = await _seed_pending_document(mongo_db, tenant_id, source, title)

    # Upload a real markdown payload via the FilesystemBlobStore.
    from src.services.blobstore import get_blob_store

    payload = b"# Test\n\nHello world. " + b"x " * 200
    import io

    blob_store = get_blob_store()
    key = f"{tenant_id}/{document_id}/{source}"
    blob_uri = await blob_store.put(key, io.BytesIO(payload), "text/markdown")

    # Run the worker body. ``ingest_document`` is sync (uses asyncio.run
    # internally) so we hop to a thread to avoid running asyncio inside asyncio.
    await asyncio.to_thread(_run_worker_task, blob_uri, document_id, tenant_id, source, title)

    doc = await mongo_db["documents"].find_one({"_id": document_id})
    assert doc is not None, "document record vanished"
    assert doc["status"] == "ready", (
        f"expected ready, got {doc['status']!r} ({doc.get('error_message')!r})"
    )
    assert doc["chunk_count"] >= 1

    chunk = await mongo_db["chunks"].find_one({"document_id": document_id})
    assert chunk is not None, "no chunk written"
    # Bug B regression: chunked content must never be the worker's error placeholder.
    assert not chunk["content"].startswith("[Error:"), (
        f"Bug B regression: chunk leaked error placeholder: {chunk['content']!r}"
    )


async def test_ingestion_missing_blob_marks_failed(mongo_db, tmp_path, monkeypatch) -> None:
    """Race the blob delete: worker must mark the doc failed, not silent-corrupt."""
    _patch_worker_for_test_db(monkeypatch, mongo_db, tmp_path)

    tenant_id = "tenant-it-missing"
    source = "test.md"
    title = "Test"

    document_id = await _seed_pending_document(mongo_db, tenant_id, source, title)

    from src.services.blobstore import get_blob_store

    blob_store = get_blob_store()
    import io

    key = f"{tenant_id}/{document_id}/{source}"
    blob_uri = await blob_store.put(key, io.BytesIO(b"# Test"), "text/markdown")

    # Race condition: blob is deleted before the worker can read it.
    shutil.rmtree(tmp_path, ignore_errors=True)

    await asyncio.to_thread(_run_worker_task, blob_uri, document_id, tenant_id, source, title)

    doc = await mongo_db["documents"].find_one({"_id": document_id})
    assert doc is not None
    assert doc["status"] == "failed", f"expected failed, got {doc['status']!r}"
    assert doc.get("chunk_count", 0) == 0
    assert "blob_not_found" in (doc.get("error_message") or "").lower(), (
        f"expected error_message to mention blob_not_found, got {doc.get('error_message')!r}"
    )


async def test_post_success_exception_does_not_mark_failed(mongo_db, tmp_path, monkeypatch) -> None:
    """Regression: if cleanup/log raises after update_status(READY), the doc
    must NOT be flipped to FAILED on the same call.

    Strategy: monkeypatch ``_safe_delete`` in ``src.worker`` to raise after
    the success path commits. The broad except must observe ``committed=True``
    and short-circuit to a "ready" return without mutating the document.
    """
    pytest.importorskip("docling")  # heavyweight optional dep

    _patch_worker_for_test_db(monkeypatch, mongo_db, tmp_path)

    tenant_id = "tenant-it-postsuccess"
    source = "test.md"
    title = "Test"

    document_id = await _seed_pending_document(mongo_db, tenant_id, source, title)

    from src.services.blobstore import get_blob_store

    payload = b"# Test\n\nHello world. " + b"x " * 200
    import io

    blob_store = get_blob_store()
    key = f"{tenant_id}/{document_id}/{source}"
    blob_uri = await blob_store.put(key, io.BytesIO(payload), "text/markdown")

    # Patch _safe_delete to raise on the success-path call. This simulates
    # a transient blob-delete failure happening AFTER update_status(READY).
    from src import worker as worker_module

    async def _raising_safe_delete(_blob_store, _blob_uri):
        raise RuntimeError("simulated post-success delete failure")

    monkeypatch.setattr(worker_module, "_safe_delete", _raising_safe_delete)

    result = await asyncio.to_thread(
        _run_worker_task, blob_uri, document_id, tenant_id, source, title
    )

    # Doc must remain READY despite the post-success exception.
    doc = await mongo_db["documents"].find_one({"_id": document_id})
    assert doc is not None
    assert doc["status"] == "ready", (
        f"post-success exception flipped doc to {doc['status']!r}: {doc.get('error_message')!r}"
    )
    assert doc.get("chunk_count", 0) >= 1

    # And the task return shape says ready, not failed.
    assert result.successful(), f"task didn't complete cleanly: {result.traceback}"
    payload_out = result.get(disable_sync_subtasks=False)
    assert payload_out["status"] == "ready"


async def test_chunks_never_contain_error_placeholder(mongo_db) -> None:
    """Bug B regression scan: no chunk in the DB starts with '[Error:'.

    Runs against the per-test database created by the ``mongo_db`` fixture,
    so it cannot pollute or be polluted by other suites. If/when an integration
    suite is wired against a longer-lived database, this scan will start
    catching real regressions in CI.
    """
    cursor = mongo_db["chunks"].find({"content": {"$regex": r"^\[Error:"}})
    leaked = await cursor.to_list(length=1)
    assert leaked == [], f"Found Bug B casualties: {leaked}"
