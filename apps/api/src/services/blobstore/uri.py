"""URI parsing and tenant ownership assertions for BlobStore URIs."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlparse


class InvalidBlobURIError(ValueError):
    """URI scheme/shape is not recognized."""


class TenantOwnershipError(PermissionError):
    """The tenant in the URI does not match the expected tenant_id."""


def assert_tenant_owns_uri(
    uri: str,
    tenant_id: str,
    upload_root: str | None = None,
) -> None:
    """Verify the URI's tenant prefix matches `tenant_id`.

    Args:
        uri: BlobStore URI (supabase://... or file://...).
        tenant_id: Expected tenant ID from the verified Principal.
        upload_root: For file:// URIs, the absolute path under which all blobs live.
            When None, falls back to settings.upload_temp_dir.

    Raises:
        InvalidBlobURIError: if the URI is not a recognized scheme/shape.
        TenantOwnershipError: if the tenant prefix does not match.
    """
    parsed = urlparse(uri)
    if parsed.scheme == "supabase":
        # supabase://<bucket>/<tenant>/<doc>/<file>
        # `netloc` is the bucket; `path` is /tenant/doc/file
        decoded_path = unquote(parsed.path)
        path_parts = decoded_path.lstrip("/").split("/", 1)
        if not path_parts or not path_parts[0]:
            raise InvalidBlobURIError(f"missing tenant segment: {uri}")
        tenant_segment = path_parts[0]
        # Defensive: reject suspicious characters in the tenant segment.
        if any(c in tenant_segment for c in ("/", "..", "%", "\x00")):
            raise InvalidBlobURIError(f"unsafe tenant segment {tenant_segment!r} in: {uri}")
        if tenant_segment != tenant_id:
            raise TenantOwnershipError(
                f"tenant mismatch: uri={tenant_segment!r} expected={tenant_id!r}"
            )
        return

    if parsed.scheme == "file":
        if upload_root is None:
            from src.core.settings import load_settings

            upload_root = load_settings().upload_temp_dir
        root = Path(upload_root).resolve()
        # Percent-decode the URI path before resolving so percent-encoded
        # legitimate access (e.g. file:///tmp/uploads/tenant%2da/...) matches
        # the on-disk decoded path. Mirrors the supabase:// branch (Med-2).
        decoded_path = unquote(parsed.path)
        # Reject null bytes BEFORE resolve() (which would raise ValueError
        # from lstat with a less-clear error).
        if "\x00" in decoded_path:
            raise InvalidBlobURIError(f"unsafe null byte in path: {uri}")
        target = Path(decoded_path).resolve()
        try:
            rel = target.relative_to(root)
        except ValueError as e:
            raise InvalidBlobURIError(f"file URI escapes upload_root: {uri}") from e
        if not rel.parts:
            raise TenantOwnershipError(f"tenant mismatch: uri=None expected={tenant_id!r}")
        tenant_segment = rel.parts[0]
        # Defensive: reject suspicious characters in the tenant segment
        # (mirrors the supabase:// branch). "/" cannot appear because
        # rel.parts already split on the separator.
        if any(c in tenant_segment for c in ("..", "%", "\x00")):
            raise InvalidBlobURIError(f"unsafe tenant segment {tenant_segment!r} in: {uri}")
        if tenant_segment != tenant_id:
            raise TenantOwnershipError(
                f"tenant mismatch: uri={tenant_segment!r} expected={tenant_id!r}"
            )
        return

    raise InvalidBlobURIError(f"unrecognized scheme: {parsed.scheme}")


def extract_extension(uri: str) -> str:
    """Return the file extension from the URI (lowercase, includes leading dot)."""
    parsed = urlparse(uri)
    return os.path.splitext(parsed.path)[1].lower()
