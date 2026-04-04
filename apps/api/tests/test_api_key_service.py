"""Tests for API key service."""

import hashlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId


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


@pytest.mark.unit
async def test_validate_key_returns_tenant_data(mock_api_keys_collection):
    """validate_key returns tenant_id and permissions for a valid key."""
    from src.services.api_key import APIKeyService

    raw_key = "mrag_testkey12345678901234567890123456"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    mock_api_keys_collection.find_one.return_value = {
        "_id": ObjectId(),
        "tenant_id": "tenant-abc",
        "key_hash": key_hash,
        "permissions": ["chat", "search"],
        "is_revoked": False,
    }

    service = APIKeyService(api_keys_collection=mock_api_keys_collection)
    result = await service.validate_key(raw_key)

    assert result is not None
    assert result["tenant_id"] == "tenant-abc"
    assert result["permissions"] == ["chat", "search"]
    assert "key_id" in result

    # Verify lookup used the hash
    mock_api_keys_collection.find_one.assert_called_once_with({"key_hash": key_hash})


@pytest.mark.unit
async def test_validate_key_unknown_returns_none(mock_api_keys_collection):
    """validate_key returns None for an unknown key."""
    from src.services.api_key import APIKeyService

    mock_api_keys_collection.find_one.return_value = None

    service = APIKeyService(api_keys_collection=mock_api_keys_collection)
    result = await service.validate_key("mrag_nonexistentkey1234567890123456")

    assert result is None


@pytest.mark.unit
async def test_validate_key_revoked_returns_none(mock_api_keys_collection):
    """validate_key returns None for a revoked key."""
    from src.services.api_key import APIKeyService

    raw_key = "mrag_revokedkey12345678901234567890123"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    mock_api_keys_collection.find_one.return_value = {
        "_id": ObjectId(),
        "tenant_id": "tenant-abc",
        "key_hash": key_hash,
        "permissions": ["chat"],
        "is_revoked": True,
    }

    service = APIKeyService(api_keys_collection=mock_api_keys_collection)
    result = await service.validate_key(raw_key)

    assert result is None


@pytest.mark.unit
async def test_list_keys_returns_tenant_keys(mock_api_keys_collection):
    """list_keys returns keys for the given tenant only."""
    from src.services.api_key import APIKeyService

    key_id = ObjectId()
    mock_cursor = MagicMock()
    mock_cursor.sort = MagicMock(return_value=mock_cursor)
    mock_cursor.to_list = AsyncMock(
        return_value=[
            {
                "_id": key_id,
                "tenant_id": "tenant-abc",
                "key_prefix": "7kB2xR9m",
                "name": "Production",
                "permissions": ["chat", "search"],
                "is_revoked": False,
                "last_used_at": None,
                "created_at": datetime(2026, 4, 1, tzinfo=timezone.utc),
            }
        ]
    )
    mock_api_keys_collection.find = MagicMock(return_value=mock_cursor)

    service = APIKeyService(api_keys_collection=mock_api_keys_collection)
    result = await service.list_keys("tenant-abc")

    assert len(result) == 1
    assert result[0]["id"] == str(key_id)
    assert result[0]["key_prefix"] == "7kB2xR9m"
    assert result[0]["name"] == "Production"
    assert "key_hash" not in result[0]

    # Verify query filtered by tenant_id and projected out key_hash
    mock_api_keys_collection.find.assert_called_once()
    find_args = mock_api_keys_collection.find.call_args
    assert find_args[0][0] == {"tenant_id": "tenant-abc"}
    assert find_args[0][1]["key_hash"] == 0  # Projected out


@pytest.mark.unit
async def test_revoke_key_sets_is_revoked(mock_api_keys_collection):
    """revoke_key sets is_revoked=True for the correct key and tenant."""
    from src.services.api_key import APIKeyService

    key_id = ObjectId()
    mock_api_keys_collection.update_one.return_value = MagicMock(matched_count=1)

    service = APIKeyService(api_keys_collection=mock_api_keys_collection)
    result = await service.revoke_key(str(key_id), "tenant-abc")

    assert result is True

    mock_api_keys_collection.update_one.assert_called_once()
    call_args = mock_api_keys_collection.update_one.call_args
    assert call_args[0][0] == {"_id": key_id, "tenant_id": "tenant-abc"}
    assert call_args[0][1] == {"$set": {"is_revoked": True}}


@pytest.mark.unit
async def test_revoke_key_wrong_tenant_returns_false(mock_api_keys_collection):
    """revoke_key returns False when key doesn't belong to tenant."""
    from src.services.api_key import APIKeyService

    key_id = ObjectId()
    mock_api_keys_collection.update_one.return_value = MagicMock(matched_count=0)

    service = APIKeyService(api_keys_collection=mock_api_keys_collection)
    result = await service.revoke_key(str(key_id), "wrong-tenant")

    assert result is False
