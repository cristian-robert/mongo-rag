"""Tests for worker retry semantics — BlobAccessError must retry, BlobNotFoundError terminal."""

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
