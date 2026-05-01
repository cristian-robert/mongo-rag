"""Tests for worker retry semantics — BlobAccessError must retry, BlobNotFoundError terminal."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.blobstore import BlobAccessError, BlobNotFoundError


@pytest.fixture(autouse=True)
def _reset_cache():
    from src.services.blobstore.factory import reset_blob_store_cache

    reset_blob_store_cache()
    yield
    reset_blob_store_cache()


def test_ingest_document_lists_blob_access_error_in_autoretry():
    """Regression: BlobAccessError must be in autoretry_for or retries silently fail."""
    from src.worker import ingest_document

    assert BlobAccessError in ingest_document.autoretry_for, (
        f"BlobAccessError missing from autoretry_for={ingest_document.autoretry_for}; "
        "transient blob errors will fail on first attempt instead of retrying"
    )


def test_ingest_url_lists_blob_access_error_in_autoretry():
    from src.worker import ingest_url

    assert BlobAccessError in ingest_url.autoretry_for


def test_blob_not_found_not_in_autoretry():
    """BlobNotFoundError must be terminal — never retried."""
    from src.worker import ingest_document, ingest_url

    assert BlobNotFoundError not in ingest_document.autoretry_for
    assert BlobNotFoundError not in ingest_url.autoretry_for


def _captured_emit_kwargs(mock_emit):
    """Return the kwargs of the first call to the mocked _emit_ingestion_complete."""
    assert mock_emit.called, "_emit_ingestion_complete was not called"
    return mock_emit.call_args.kwargs


def test_url_fetch_failure_emits_blob_read_failed_false():
    """URLFetchError happens before put() — no blob exists, blob_read_failed must be False."""
    from src.services.ingestion.url_loader import URLFetchError
    from src.worker import ingest_url

    fake_client = MagicMock()
    fake_client.close = AsyncMock(return_value=None)
    fake_db = MagicMock()
    fake_client.__getitem__.return_value = fake_db
    fake_db.__getitem__.return_value = MagicMock()

    fake_service = MagicMock()
    fake_service.update_status = AsyncMock(return_value=None)

    with (
        patch("pymongo.AsyncMongoClient", return_value=fake_client),
        patch("src.services.ingestion.service.IngestionService", return_value=fake_service),
        patch(
            "src.services.ingestion.url_loader.fetch_url",
            new=AsyncMock(side_effect=URLFetchError("connection refused")),
        ),
        patch("src.worker._emit_ingestion_complete") as mock_emit,
    ):
        result = ingest_url.run(
            url="https://example.com/page",
            document_id="doc-fetch-fail",
            tenant_id="t1",
        )

    assert result["status"] == "failed"
    kwargs = _captured_emit_kwargs(mock_emit)
    assert kwargs["blob_read_failed"] is False, (
        "URLFetchError happens BEFORE blob_store.put() — no blob has been written or read, "
        "so blob_read_failed must be False to keep the metric truthful."
    )
    assert kwargs["blob_uri"] is None
    assert kwargs["status"] == "failed"
    assert kwargs["source_kind"] == "url"


def test_url_validation_failure_emits_blob_read_failed_false():
    """URLValidationError also happens before put() — sanity-check it stays False."""
    from src.services.ingestion.url_loader import URLValidationError
    from src.worker import ingest_url

    fake_client = MagicMock()
    fake_client.close = AsyncMock(return_value=None)
    fake_db = MagicMock()
    fake_client.__getitem__.return_value = fake_db
    fake_db.__getitem__.return_value = MagicMock()

    fake_service = MagicMock()
    fake_service.update_status = AsyncMock(return_value=None)

    with (
        patch("pymongo.AsyncMongoClient", return_value=fake_client),
        patch("src.services.ingestion.service.IngestionService", return_value=fake_service),
        patch(
            "src.services.ingestion.url_loader.fetch_url",
            new=AsyncMock(side_effect=URLValidationError("private IP rejected")),
        ),
        patch("src.worker._emit_ingestion_complete") as mock_emit,
    ):
        result = ingest_url.run(
            url="http://127.0.0.1/secret",
            document_id="doc-val-fail",
            tenant_id="t1",
        )

    assert result["status"] == "failed"
    kwargs = _captured_emit_kwargs(mock_emit)
    assert kwargs["blob_read_failed"] is False
    assert kwargs["blob_uri"] is None


def test_will_celery_retry_returns_true_for_blob_access_error_with_retries_left():
    """_will_celery_retry must say YES so the worker preserves PROCESSING state."""
    from src.worker import _will_celery_retry, ingest_document

    fake_task = MagicMock()
    fake_task.autoretry_for = ingest_document.autoretry_for
    fake_task.max_retries = ingest_document.max_retries
    fake_task.request.retries = 0

    assert _will_celery_retry(fake_task, BlobAccessError("transient 503")) is True


def test_will_celery_retry_returns_false_when_retries_exhausted():
    from src.worker import _will_celery_retry, ingest_document

    fake_task = MagicMock()
    fake_task.autoretry_for = ingest_document.autoretry_for
    fake_task.max_retries = ingest_document.max_retries
    fake_task.request.retries = ingest_document.max_retries  # exhausted

    assert _will_celery_retry(fake_task, BlobAccessError("transient")) is False


def test_will_celery_retry_returns_false_for_non_retryable_exception():
    from src.worker import _will_celery_retry, ingest_document

    fake_task = MagicMock()
    fake_task.autoretry_for = ingest_document.autoretry_for
    fake_task.max_retries = ingest_document.max_retries
    fake_task.request.retries = 0

    # ValueError is not in autoretry_for → Celery won't retry → terminal.
    assert _will_celery_retry(fake_task, ValueError("bad input")) is False


def test_url_blob_access_error_emits_blob_read_failed_true_on_terminal():
    """A BlobAccessError raised during the URL-path blob put/open phase must
    surface as blob_read_failed=True on the terminal (retries-exhausted)
    ingestion_complete emit — otherwise the dashboard mis-classifies the
    failure as non-blob.
    """
    from src.services.ingestion.url_loader import FetchedURL
    from src.worker import ingest_url

    fake_client = MagicMock()
    fake_client.close = AsyncMock(return_value=None)
    fake_db = MagicMock()
    fake_client.__getitem__.return_value = fake_db
    fake_db.__getitem__.return_value = MagicMock()

    fake_service = MagicMock()
    fake_service.update_status = AsyncMock(return_value=None)

    # fetch_url succeeds — failure is downstream at blob_store.put().
    fake_fetched = FetchedURL(
        url="https://example.com/page",
        final_url="https://example.com/page",
        content=b"<html><body>hi</body></html>",
        content_type="text/html",
        charset="utf-8",
    )

    # BlobStore whose .put() raises BlobAccessError (transient upstream 5xx).
    fake_blob_store = MagicMock()
    fake_blob_store.put = AsyncMock(side_effect=BlobAccessError("transient 503 from Storage"))

    with (
        patch("pymongo.AsyncMongoClient", return_value=fake_client),
        patch("src.services.ingestion.service.IngestionService", return_value=fake_service),
        patch(
            "src.services.ingestion.url_loader.fetch_url",
            new=AsyncMock(return_value=fake_fetched),
        ),
        patch("src.services.blobstore.get_blob_store", return_value=fake_blob_store),
        patch("src.worker._emit_ingestion_complete") as mock_emit,
        patch("src.worker._safe_delete", new=AsyncMock(return_value=None)),
    ):
        result = ingest_url.apply(
            kwargs={
                "url": "https://example.com/page",
                "document_id": "doc-url-blob-fail",
                "tenant_id": "t1",
            },
            throw=False,
        )

    # autoretry exhausts → final attempt re-raises BlobAccessError.
    assert result.failed()
    assert isinstance(result.result, BlobAccessError)

    # Exactly one emit (final terminal attempt) — and it must reflect the blob failure.
    assert mock_emit.call_count == 1, (
        f"ingestion_complete must only emit on terminal attempt; got {mock_emit.call_count}"
    )
    kwargs = mock_emit.call_args.kwargs
    assert kwargs["blob_read_failed"] is True, (
        "BlobAccessError raised during the URL-path blob put/open phase must "
        "set blob_read_failed=True so dashboards classify the failure correctly. "
        f"got kwargs={kwargs!r}"
    )
    assert kwargs["status"] == "failed"
    assert kwargs["source_kind"] == "url"


def test_blob_access_error_during_open_keeps_doc_in_processing_until_retries_exhausted():
    """A retryable BlobAccessError during streaming must NOT flip doc → FAILED on each retry.

    The worker must propagate the exception so Celery autoretry can pick it up,
    while leaving doc.status as PROCESSING and skipping ingestion_complete emit
    for every attempt EXCEPT the final one (retries exhausted). Otherwise the
    dashboard sees a transient FAILED → READY flap on each retry.

    We invoke ``ingest_document.apply()`` which runs the full Celery autoretry
    chain inline. With ``max_retries=3`` we expect 4 attempts; the first 3 must
    NOT mark the doc FAILED or emit ingestion_complete. Only the 4th (final)
    attempt is allowed to mark FAILED and emit.
    """
    from src.worker import ingest_document

    # Mongo plumbing — record every update_status call so we can assert on order.
    status_calls = []

    fake_client = MagicMock()
    fake_client.close = AsyncMock(return_value=None)
    fake_db = MagicMock()
    fake_client.__getitem__.return_value = fake_db
    fake_db.__getitem__.return_value = MagicMock()

    async def _track_update_status(doc_id, tenant, status, **kwargs):
        status_calls.append(str(status))

    fake_service = MagicMock()
    fake_service.update_status = AsyncMock(side_effect=_track_update_status)

    # Blob store whose .open() context manager raises BlobAccessError.
    class _FailingOpen:
        async def __aenter__(self):
            raise BlobAccessError("transient 5xx from Storage")

        async def __aexit__(self, *a):
            return False

    fake_blob_store = MagicMock()
    fake_blob_store.open.return_value = _FailingOpen()

    with (
        patch("pymongo.AsyncMongoClient", return_value=fake_client),
        patch("src.services.ingestion.service.IngestionService", return_value=fake_service),
        patch("src.services.blobstore.get_blob_store", return_value=fake_blob_store),
        patch("src.services.blobstore.assert_tenant_owns_uri", return_value=None),
        patch("src.worker._emit_ingestion_complete") as mock_emit,
        patch("src.worker._safe_delete", new=AsyncMock(return_value=None)),
    ):
        result = ingest_document.apply(
            kwargs={
                "blob_uri": "file:///tmp/t1/doc-rt/test.md",
                "document_id": "doc-rt",
                "tenant_id": "t1",
                "title": "T",
                "source": "test.md",
                "metadata": {},
            },
            throw=False,
        )

    # The task ultimately raises (retries exhausted) — Celery surfaces it.
    assert result.failed()
    assert isinstance(result.result, BlobAccessError)

    # Total max_retries+1 attempts, each starts with PROCESSING; only the last
    # attempt (retries exhausted) escalates to FAILED. This is the regression
    # bar: prior to the fix, EVERY attempt marked FAILED before re-raising.
    failed_calls = [s for s in status_calls if "FAILED" in s]
    processing_calls = [s for s in status_calls if "PROCESSING" in s]
    assert len(processing_calls) == ingest_document.max_retries + 1, (
        f"expected one PROCESSING update per attempt; got {status_calls!r}"
    )
    assert len(failed_calls) == 1, (
        "doc must only flip to FAILED on the FINAL exhausted attempt — "
        f"got {failed_calls!r} from full sequence {status_calls!r}"
    )

    # Likewise: ingestion_complete must fire exactly once (final terminal attempt).
    assert mock_emit.call_count == 1, (
        f"ingestion_complete must only emit on the final (terminal) attempt; "
        f"got {mock_emit.call_count} calls"
    )
