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
