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
