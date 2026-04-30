"""BlobStore Protocol, errors, and shared helpers."""

from __future__ import annotations

import unicodedata
from typing import (
    AsyncContextManager,
    AsyncIterator,
    BinaryIO,
    Protocol,
    runtime_checkable,
)

_MAX_FILENAME_LEN = 255


class BlobStoreError(Exception):
    """Base class for BlobStore failures."""


class BlobNotFoundError(BlobStoreError):
    """The requested blob does not exist. Terminal — do not retry."""


class BlobAccessError(BlobStoreError):
    """Transient failure (5xx, network, timeout). Retryable."""


def sanitize_filename(name: str) -> str:
    """Reject path traversal, normalize unicode, cap length at 255 chars.

    Raises:
        ValueError: if `name` is empty or sanitizes down to empty.
    """
    if not name:
        raise ValueError("filename is empty")
    normalized = unicodedata.normalize("NFKC", name)
    cleaned = normalized.replace("/", "").replace("\\", "")
    cleaned = cleaned.lstrip(".")  # remove leading dots (.., .hidden, etc.)
    if not cleaned:
        raise ValueError("filename is empty after sanitization")
    return cleaned[:_MAX_FILENAME_LEN]


@runtime_checkable
class BlobStore(Protocol):
    """Object-storage abstraction for ingestion handoff."""

    async def put(
        self,
        key: str,
        source: BinaryIO | AsyncIterator[bytes],
        content_type: str | None = None,
    ) -> str:
        """Stream `source` to `key`. Returns the URI (e.g. supabase://bucket/key, file:///abs)."""
        ...

    def open(self, uri: str) -> AsyncContextManager[AsyncIterator[bytes]]:
        """Stream bytes back. Raises BlobNotFoundError on 404, BlobAccessError on transient 5xx/network."""
        ...

    async def delete(self, uri: str) -> None:
        """Idempotent. Logs but never raises on Supabase errors — lifecycle rule is the safety net."""
        ...

    async def signed_url(self, uri: str, expires_in: int = 3600) -> str:
        """Declared in Protocol; not called by ingestion. Reserved for future dashboard download."""
        ...
