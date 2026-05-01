"""SupabaseBlobStore — S3-compatible BlobStore backed by Supabase Storage."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError

from src.services.blobstore.base import BlobAccessError, BlobNotFoundError

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 64 * 1024


class SupabaseBlobStore:
    """boto3 against the Supabase Storage S3-compatible endpoint. URI scheme: supabase://.

    Authenticates with a DISTINCT S3 access-key/secret pair minted under the Supabase
    dashboard (Project Settings → Storage → S3 Connection). These are NOT the
    service-role JWT-signing key (`SUPABASE_SECRET_KEY`); using the service-role key
    here returns SignatureDoesNotMatch / 403 from Supabase Storage's S3-compat layer.
    """

    def __init__(
        self,
        bucket: str,
        supabase_url: str,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1",
        endpoint_url: str | None | object = ...,  # sentinel: ... means "derive from supabase_url"
    ) -> None:
        self._bucket = bucket
        if endpoint_url is ...:
            endpoint_url = f"{supabase_url.rstrip('/')}/storage/v1/s3"
        kwargs = {
            "service_name": "s3",
            "region_name": region,
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
        }
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url
        self._client = boto3.client(**kwargs)

    async def put(self, key: str, source, content_type: str | None = None) -> str:
        # boto3 upload_fileobj is sync but streams; run in threadpool for non-blocking.
        import asyncio

        if hasattr(source, "read"):
            extra = {"ContentType": content_type} if content_type else {}
            await asyncio.to_thread(
                self._client.upload_fileobj,
                source,
                self._bucket,
                key,
                ExtraArgs=extra,
            )
        else:
            # AsyncIterator → buffer to a SpooledTemporaryFile, then upload.
            import tempfile

            with tempfile.SpooledTemporaryFile(max_size=_CHUNK_SIZE * 16) as buf:
                async for chunk in source:
                    buf.write(chunk)
                buf.seek(0)
                extra = {"ContentType": content_type} if content_type else {}
                await asyncio.to_thread(
                    self._client.upload_fileobj,
                    buf,
                    self._bucket,
                    key,
                    ExtraArgs=extra,
                )
        return f"supabase://{self._bucket}/{key}"

    @asynccontextmanager
    async def open(self, uri: str) -> AsyncIterator[AsyncIterator[bytes]]:
        bucket, key = self._parse(uri)
        import asyncio

        try:
            obj = await asyncio.to_thread(self._client.get_object, Bucket=bucket, Key=key)
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            if code in ("NoSuchKey", "404"):
                raise BlobNotFoundError(f"blob not found: {uri}") from e
            raise BlobAccessError(f"s3 error: {code}") from e

        body = obj["Body"]

        async def _stream() -> AsyncIterator[bytes]:
            try:
                while True:
                    chunk = await asyncio.to_thread(body.read, _CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk
            finally:
                body.close()

        yield _stream()

    async def delete(self, uri: str) -> None:
        import asyncio

        try:
            bucket, key = self._parse(uri)
            await asyncio.to_thread(self._client.delete_object, Bucket=bucket, Key=key)
        except ClientError as e:
            # Idempotent + non-blocking — log and swallow. Lifecycle rule is the safety net.
            logger.warning("blob_delete_failed", extra={"uri": uri, "error": str(e)})
        except Exception as e:
            logger.warning("blob_delete_failed", extra={"uri": uri, "error": str(e)})

    async def signed_url(self, uri: str, expires_in: int = 3600) -> str:
        import asyncio

        bucket, key = self._parse(uri)
        url = await asyncio.to_thread(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        return url

    def _parse(self, uri: str) -> tuple[str, str]:
        parsed = urlparse(uri)
        if parsed.scheme != "supabase":
            raise ValueError(f"not a supabase:// URI: {uri}")
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
        return bucket, key
