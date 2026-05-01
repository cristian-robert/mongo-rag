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


def test_supabase_without_access_key_raises(monkeypatch):
    monkeypatch.setenv("BLOB_STORE", "supabase")
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "mongorag-uploads")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_S3_SECRET_KEY", "s")
    monkeypatch.delenv("SUPABASE_S3_ACCESS_KEY", raising=False)
    with pytest.raises(ValueError, match="SUPABASE_S3_ACCESS_KEY"):
        get_blob_store()


def test_supabase_without_secret_key_raises(monkeypatch):
    monkeypatch.setenv("BLOB_STORE", "supabase")
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "mongorag-uploads")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_S3_ACCESS_KEY", "a")
    monkeypatch.delenv("SUPABASE_S3_SECRET_KEY", raising=False)
    with pytest.raises(ValueError, match="SUPABASE_S3_SECRET_KEY"):
        get_blob_store()
