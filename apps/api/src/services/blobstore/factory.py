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


def _require_secret(settings) -> str:  # noqa: ANN001
    # Supabase secret-key handling lives in core/postgres for DB; for storage
    # we read the same secret env. Importing here avoids a circular dep.
    import os

    secret = os.environ.get("SUPABASE_SECRET_KEY")
    if not secret:
        raise ValueError("SUPABASE_SECRET_KEY is required when BLOB_STORE='supabase'")
    return secret
