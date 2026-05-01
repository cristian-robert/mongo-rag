"""FilesystemBlobStore — file:// backed BlobStore for tests and local dev."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, BinaryIO
from urllib.parse import urlparse

from src.services.blobstore.base import (
    BlobAccessError,
    BlobNotFoundError,
)

_CHUNK_SIZE = 64 * 1024  # 64 KiB


class FilesystemBlobStore:
    """Stores blobs on the local filesystem under `root`. URI scheme: file://."""

    def __init__(self, root: str) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    async def put(
        self,
        key: str,
        source: BinaryIO | AsyncIterator[bytes],
        content_type: str | None = None,
    ) -> str:
        # Reject absolute keys and traversal.
        if key.startswith("/") or ".." in Path(key).parts:
            raise ValueError(f"unsafe key: {key}")
        target = self._root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("wb") as dst:
                if hasattr(source, "read"):
                    while True:
                        chunk = source.read(_CHUNK_SIZE)
                        if not chunk:
                            break
                        dst.write(chunk)
                else:
                    async for chunk in source:
                        dst.write(chunk)
        except BaseException:
            # Cleanup partial file on any failure (size cap, network, etc.).
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        return f"file://{target}"

    @asynccontextmanager
    async def open(self, uri: str) -> AsyncIterator[AsyncIterator[bytes]]:
        path = self._path_from_uri(uri)
        if not path.exists():
            raise BlobNotFoundError(f"blob not found: {uri}")

        async def _stream() -> AsyncIterator[bytes]:
            try:
                with path.open("rb") as src:
                    while True:
                        chunk = src.read(_CHUNK_SIZE)
                        if not chunk:
                            break
                        yield chunk
            except OSError as e:
                raise BlobAccessError(f"read failed: {uri}") from e

        yield _stream()

    async def delete(self, uri: str) -> None:
        path = self._path_from_uri(uri)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            # Idempotent — never raise on cleanup.
            pass

    async def signed_url(self, uri: str, expires_in: int = 3600) -> str:
        # No-op for local fs. The URI is already directly usable by the worker.
        return uri

    def _path_from_uri(self, uri: str) -> Path:
        parsed = urlparse(uri)
        if parsed.scheme != "file":
            raise ValueError(f"not a file:// URI: {uri}")
        # urlparse for file:///abs/path puts the abs path in `path`.
        return Path(parsed.path)
