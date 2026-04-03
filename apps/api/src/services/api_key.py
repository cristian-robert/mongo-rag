"""API key service: generation, validation, listing, revocation."""

import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import Any

from pymongo.asynchronous.collection import AsyncCollection

logger = logging.getLogger(__name__)

# Base62 alphabet: 0-9, A-Z, a-z
_BASE62_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def _base62_encode(data: bytes) -> str:
    """Encode bytes to base62 string."""
    num = int.from_bytes(data, byteorder="big")
    if num == 0:
        return _BASE62_ALPHABET[0]
    chars = []
    while num > 0:
        num, remainder = divmod(num, 62)
        chars.append(_BASE62_ALPHABET[remainder])
    return "".join(reversed(chars))


def _generate_key() -> tuple[str, str, str]:
    """Generate a new API key.

    Returns:
        Tuple of (raw_key, key_hash, key_prefix).
    """
    raw_bytes = secrets.token_bytes(32)
    encoded = _base62_encode(raw_bytes)
    raw_key = f"mrag_{encoded}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = encoded[:8]
    return raw_key, key_hash, key_prefix


class APIKeyService:
    """Handles API key generation, validation, listing, and revocation."""

    def __init__(self, api_keys_collection: AsyncCollection) -> None:
        self._api_keys = api_keys_collection

    async def create_key(
        self, tenant_id: str, name: str, permissions: list[str]
    ) -> dict[str, Any]:
        """Generate a new API key and store its hash.

        Args:
            tenant_id: Tenant this key belongs to.
            name: Human-readable key name.
            permissions: Allowed operations.

        Returns:
            Dict with raw_key (shown once), key_prefix, name, permissions, created_at.
        """
        raw_key, key_hash, key_prefix = _generate_key()
        now = datetime.now(timezone.utc)

        doc = {
            "tenant_id": tenant_id,
            "key_hash": key_hash,
            "key_prefix": key_prefix,
            "name": name,
            "permissions": permissions,
            "is_revoked": False,
            "last_used_at": None,
            "created_at": now,
        }
        await self._api_keys.insert_one(doc)

        logger.info(
            "api_key_created",
            extra={"tenant_id": tenant_id, "key_prefix": key_prefix, "name": name},
        )

        return {
            "raw_key": raw_key,
            "key_prefix": key_prefix,
            "name": name,
            "permissions": permissions,
            "created_at": now,
        }
