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
