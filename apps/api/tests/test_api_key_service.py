"""Tests for API key service."""

import hashlib
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_api_keys_collection():
    """Create mock api_keys collection."""
    collection = MagicMock()
    collection.insert_one = AsyncMock()
    collection.find_one = AsyncMock(return_value=None)
    collection.update_one = AsyncMock()
    return collection


@pytest.mark.unit
async def test_create_key_returns_raw_key_with_prefix(mock_api_keys_collection):
    """create_key returns a raw key starting with 'mrag_'."""
    from src.services.api_key import APIKeyService

    service = APIKeyService(api_keys_collection=mock_api_keys_collection)
    result = await service.create_key(
        tenant_id="tenant-abc", name="Test Key", permissions=["chat", "search"]
    )

    assert result["raw_key"].startswith("mrag_")
    assert len(result["raw_key"]) > 20
    assert result["name"] == "Test Key"
    assert result["permissions"] == ["chat", "search"]
    assert result["key_prefix"] == result["raw_key"][5:13]  # First 8 chars after 'mrag_'
    assert result["created_at"] is not None


@pytest.mark.unit
async def test_create_key_stores_sha256_hash(mock_api_keys_collection):
    """create_key stores SHA-256 hash of the raw key, not the key itself."""
    from src.services.api_key import APIKeyService

    service = APIKeyService(api_keys_collection=mock_api_keys_collection)
    result = await service.create_key(
        tenant_id="tenant-abc", name="Test Key", permissions=["chat"]
    )

    # Verify insert_one was called
    mock_api_keys_collection.insert_one.assert_called_once()
    stored_doc = mock_api_keys_collection.insert_one.call_args[0][0]

    # Verify hash matches
    expected_hash = hashlib.sha256(result["raw_key"].encode()).hexdigest()
    assert stored_doc["key_hash"] == expected_hash

    # Verify raw key is NOT stored
    assert "raw_key" not in stored_doc
    assert stored_doc["tenant_id"] == "tenant-abc"
    assert stored_doc["is_revoked"] is False


@pytest.mark.unit
async def test_create_key_generates_unique_keys(mock_api_keys_collection):
    """Each call to create_key generates a different raw key."""
    from src.services.api_key import APIKeyService

    service = APIKeyService(api_keys_collection=mock_api_keys_collection)
    result1 = await service.create_key(
        tenant_id="tenant-abc", name="Key 1", permissions=["chat"]
    )
    result2 = await service.create_key(
        tenant_id="tenant-abc", name="Key 2", permissions=["chat"]
    )

    assert result1["raw_key"] != result2["raw_key"]
