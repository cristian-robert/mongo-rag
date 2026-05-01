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
