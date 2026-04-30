"""Unit tests for SupabaseBlobStore against a moto-mocked S3 endpoint."""

import io

import boto3
import pytest
from moto import mock_aws

from src.services.blobstore import BlobNotFoundError
from src.services.blobstore.supabase import SupabaseBlobStore


@pytest.fixture
def mock_s3():
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="mongorag-uploads")
        yield client


@pytest.fixture
def store(mock_s3):
    # SupabaseBlobStore configured to talk to the moto-mocked S3 in-process.
    return SupabaseBlobStore(
        bucket="mongorag-uploads",
        supabase_url="https://test.supabase.co",
        secret_key="test-secret",
        region="us-east-1",
        endpoint_url=None,  # moto intercepts the default boto3 endpoint
    )


@pytest.mark.asyncio
async def test_put_returns_supabase_uri(store):
    uri = await store.put("tenant-a/doc-1/foo.txt", io.BytesIO(b"hello"), "text/plain")
    assert uri == "supabase://mongorag-uploads/tenant-a/doc-1/foo.txt"


@pytest.mark.asyncio
async def test_round_trip(store):
    payload = b"x" * 100_000
    uri = await store.put("tenant-a/doc-1/blob.bin", io.BytesIO(payload))
    out = bytearray()
    async with store.open(uri) as stream:
        async for chunk in stream:
            out.extend(chunk)
    assert bytes(out) == payload


@pytest.mark.asyncio
async def test_open_missing_raises_not_found(store):
    with pytest.raises(BlobNotFoundError):
        async with store.open("supabase://mongorag-uploads/nope/key"):
            pass


@pytest.mark.asyncio
async def test_delete_idempotent(store):
    uri = await store.put("tenant-a/doc-1/foo.txt", io.BytesIO(b"x"))
    await store.delete(uri)
    await store.delete(uri)  # second call must not raise
