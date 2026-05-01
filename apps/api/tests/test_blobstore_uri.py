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

    def test_file_uri_percent_encoded_tenant_decoded_then_matched(self, tmp_path):
        """%2da → -a; the file:// tenant segment must decode before comparison.

        Mirrors the supabase:// percent-decode parity established in Med-2.
        """
        # Create the actual on-disk path so resolve() works on real inodes.
        tenant_dir = tmp_path / "tenant-a" / "doc-1"
        tenant_dir.mkdir(parents=True)
        target = tenant_dir / "file.pdf"
        target.touch()
        # URI uses percent-encoded form; resolved path on disk uses decoded form.
        uri = f"file://{tmp_path}/tenant%2da/doc-1/file.pdf"
        assert_tenant_owns_uri(uri, "tenant-a", upload_root=str(tmp_path))

    def test_file_uri_tenant_segment_with_dotdot_rejected(self, tmp_path):
        # Construct a URI whose first path segment after upload_root contains "..".
        # The path-traversal/relative_to check would normally normalize this away,
        # but the unsafe-character check must reject it before that.
        uri = f"file://{tmp_path}/..upper/doc-1/file.pdf"
        with pytest.raises((InvalidBlobURIError, TenantOwnershipError)):
            assert_tenant_owns_uri(uri, "..upper", upload_root=str(tmp_path))

    def test_file_uri_tenant_segment_with_null_byte_rejected(self, tmp_path):
        uri = f"file://{tmp_path}/tenant%00a/doc-1/file.pdf"
        with pytest.raises(InvalidBlobURIError):
            assert_tenant_owns_uri(uri, "tenant\x00a", upload_root=str(tmp_path))

    def test_file_uri_tenant_segment_with_percent_after_decode_rejected(self, tmp_path):
        uri = f"file://{tmp_path}/%25weird/doc-1/file.pdf"
        with pytest.raises(InvalidBlobURIError):
            assert_tenant_owns_uri(uri, "%weird", upload_root=str(tmp_path))


class TestExtractExtension:
    def test_pdf(self):
        assert extract_extension("file:///x/y/file.pdf") == ".pdf"

    def test_no_extension(self):
        assert extract_extension("file:///x/y/file") == ""

    def test_supabase_uri(self):
        assert extract_extension("supabase://b/t/d/foo.docx") == ".docx"
