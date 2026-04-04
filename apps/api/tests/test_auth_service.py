"""Tests for auth service."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId

from src.services.auth import AuthService

MOCK_USER_OID = str(ObjectId())


@pytest.fixture
def mock_collections():
    """Create mock MongoDB collections for auth."""
    users = MagicMock()
    users.find_one = AsyncMock(return_value=None)
    users.insert_one = AsyncMock()
    users.update_one = AsyncMock()

    tenants = MagicMock()
    tenants.insert_one = AsyncMock()

    reset_tokens = MagicMock()
    reset_tokens.find_one = AsyncMock(return_value=None)
    reset_tokens.find_one_and_update = AsyncMock(return_value=None)
    reset_tokens.insert_one = AsyncMock()
    reset_tokens.update_many = AsyncMock()
    reset_tokens.update_one = AsyncMock()

    return {"users": users, "tenants": tenants, "reset_tokens": reset_tokens}


@pytest.mark.unit
async def test_signup_creates_tenant_and_user(mock_collections):
    """Signup creates a new tenant and user with owner role."""
    from src.services.auth import AuthService

    mock_collections["users"].insert_one.return_value = MagicMock(inserted_id="user-id-123")
    mock_collections["tenants"].insert_one.return_value = MagicMock(inserted_id="tenant-obj-id")

    service = AuthService(
        users_collection=mock_collections["users"],
        tenants_collection=mock_collections["tenants"],
        reset_tokens_collection=mock_collections["reset_tokens"],
    )

    result = await service.signup(
        email="test@example.com",
        password="securepass123",
        organization_name="Test Corp",
    )

    assert result["email"] == "test@example.com"
    assert result["user_id"] is not None
    assert result["tenant_id"] is not None

    # Verify tenant was created
    mock_collections["tenants"].insert_one.assert_called_once()
    tenant_doc = mock_collections["tenants"].insert_one.call_args[0][0]
    assert tenant_doc["name"] == "Test Corp"
    assert tenant_doc["slug"] == "test-corp"
    assert tenant_doc["plan"] == "free"

    # Verify user was created with owner role
    mock_collections["users"].insert_one.assert_called_once()
    user_doc = mock_collections["users"].insert_one.call_args[0][0]
    assert user_doc["email"] == "test@example.com"
    assert user_doc["role"] == "owner"
    assert user_doc["hashed_password"].startswith("$2b$")


@pytest.mark.unit
async def test_signup_duplicate_email_raises(mock_collections):
    """Signup with existing email raises ValueError and rolls back tenant."""
    from pymongo.errors import DuplicateKeyError

    from src.services.auth import AuthService

    # Simulate DuplicateKeyError on user insert (unique index on email)
    mock_collections["users"].insert_one = AsyncMock(
        side_effect=DuplicateKeyError("E11000 duplicate key error")
    )
    mock_collections["tenants"].delete_one = AsyncMock()

    service = AuthService(
        users_collection=mock_collections["users"],
        tenants_collection=mock_collections["tenants"],
        reset_tokens_collection=mock_collections["reset_tokens"],
    )

    with pytest.raises(ValueError, match="already registered"):
        await service.signup(
            email="test@example.com",
            password="securepass123",
            organization_name="Test Corp",
        )

    # Verify orphaned tenant was cleaned up
    mock_collections["tenants"].delete_one.assert_called_once()


@pytest.mark.unit
async def test_login_success(mock_collections):
    """Login returns user data for valid credentials."""
    from src.core.security import hash_password
    from src.services.auth import AuthService

    hashed = hash_password("securepass123")
    mock_collections["users"].find_one.return_value = {
        "_id": "user-id-123",
        "tenant_id": "tenant-abc",
        "email": "test@example.com",
        "hashed_password": hashed,
        "name": "Test User",
        "role": "owner",
        "is_active": True,
    }

    service = AuthService(
        users_collection=mock_collections["users"],
        tenants_collection=mock_collections["tenants"],
        reset_tokens_collection=mock_collections["reset_tokens"],
    )

    result = await service.login(email="test@example.com", password="securepass123")
    assert result["email"] == "test@example.com"
    assert result["tenant_id"] == "tenant-abc"
    assert result["role"] == "owner"


@pytest.mark.unit
async def test_login_wrong_password(mock_collections):
    """Login raises ValueError for wrong password."""
    from src.core.security import hash_password
    from src.services.auth import AuthService

    hashed = hash_password("securepass123")
    mock_collections["users"].find_one.return_value = {
        "_id": "user-id-123",
        "tenant_id": "tenant-abc",
        "email": "test@example.com",
        "hashed_password": hashed,
        "name": "Test User",
        "role": "owner",
        "is_active": True,
    }

    service = AuthService(
        users_collection=mock_collections["users"],
        tenants_collection=mock_collections["tenants"],
        reset_tokens_collection=mock_collections["reset_tokens"],
    )

    with pytest.raises(ValueError, match="Invalid email or password"):
        await service.login(email="test@example.com", password="wrongpassword")


@pytest.mark.unit
async def test_login_nonexistent_user(mock_collections):
    """Login raises ValueError for unknown email."""
    from src.services.auth import AuthService

    mock_collections["users"].find_one.return_value = None

    service = AuthService(
        users_collection=mock_collections["users"],
        tenants_collection=mock_collections["tenants"],
        reset_tokens_collection=mock_collections["reset_tokens"],
    )

    with pytest.raises(ValueError, match="Invalid email or password"):
        await service.login(email="nobody@example.com", password="anything")


@pytest.mark.unit
async def test_login_inactive_user(mock_collections):
    """Login raises ValueError for deactivated account."""
    from src.core.security import hash_password
    from src.services.auth import AuthService

    hashed = hash_password("securepass123")
    mock_collections["users"].find_one.return_value = {
        "_id": "user-id-123",
        "tenant_id": "tenant-abc",
        "email": "test@example.com",
        "hashed_password": hashed,
        "name": "Test User",
        "role": "owner",
        "is_active": False,
    }

    service = AuthService(
        users_collection=mock_collections["users"],
        tenants_collection=mock_collections["tenants"],
        reset_tokens_collection=mock_collections["reset_tokens"],
    )

    with pytest.raises(ValueError, match="Account is deactivated"):
        await service.login(email="test@example.com", password="securepass123")


@pytest.mark.unit
async def test_create_password_reset_token(mock_collections):
    """create_password_reset returns a raw token and stores hash."""
    from src.services.auth import AuthService

    mock_collections["users"].find_one.return_value = {
        "_id": "user-id-123",
        "email": "test@example.com",
        "tenant_id": "tenant-abc",
    }

    service = AuthService(
        users_collection=mock_collections["users"],
        tenants_collection=mock_collections["tenants"],
        reset_tokens_collection=mock_collections["reset_tokens"],
    )

    raw_token = await service.create_password_reset_token(email="test@example.com")
    assert raw_token is not None
    assert len(raw_token) > 20

    # Verify old tokens were invalidated
    mock_collections["reset_tokens"].update_many.assert_called_once()

    # Verify new token was stored as hash
    mock_collections["reset_tokens"].insert_one.assert_called_once()
    stored = mock_collections["reset_tokens"].insert_one.call_args[0][0]
    expected_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    assert stored["token_hash"] == expected_hash
    assert stored["user_id"] == "user-id-123"
    assert stored["tenant_id"] == "tenant-abc"
    assert stored["used"] is False


@pytest.mark.unit
async def test_create_password_reset_unknown_email_returns_none(mock_collections):
    """create_password_reset returns None for unknown email (no enumeration)."""
    from src.services.auth import AuthService

    mock_collections["users"].find_one.return_value = None

    service = AuthService(
        users_collection=mock_collections["users"],
        tenants_collection=mock_collections["tenants"],
        reset_tokens_collection=mock_collections["reset_tokens"],
    )

    result = await service.create_password_reset_token(email="nobody@example.com")
    assert result is None


@pytest.mark.unit
async def test_reset_password_success(mock_collections):
    """reset_password atomically claims token and updates password."""
    from src.services.auth import AuthService

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    # find_one_and_update returns the token doc (before update) when it matches
    mock_collections["reset_tokens"].find_one_and_update.return_value = {
        "_id": "token-id",
        "user_id": MOCK_USER_OID,
        "tenant_id": "tenant-abc",
        "token_hash": token_hash,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "used": False,
    }
    # User lookup for tenant validation
    mock_collections["users"].find_one.return_value = {
        "_id": ObjectId(MOCK_USER_OID),
        "tenant_id": "tenant-abc",
    }
    # user update succeeds (matched_count=1)
    mock_collections["users"].update_one.return_value = MagicMock(matched_count=1)

    service = AuthService(
        users_collection=mock_collections["users"],
        tenants_collection=mock_collections["tenants"],
        reset_tokens_collection=mock_collections["reset_tokens"],
    )

    await service.reset_password(token=raw_token, new_password="newpassword123")

    # Verify token was atomically claimed via find_one_and_update
    mock_collections["reset_tokens"].find_one_and_update.assert_called_once()
    claim_call = mock_collections["reset_tokens"].find_one_and_update.call_args
    assert claim_call[0][0]["token_hash"] == token_hash
    assert claim_call[0][0]["used"] is False
    assert claim_call[0][1] == {"$set": {"used": True}}

    # Verify password was updated with ObjectId filter
    mock_collections["users"].update_one.assert_called_once()
    update_call = mock_collections["users"].update_one.call_args
    assert update_call[0][0] == {"_id": ObjectId(MOCK_USER_OID)}
    assert update_call[0][1]["$set"]["hashed_password"].startswith("$2b$")


@pytest.mark.unit
async def test_reset_password_expired_or_used_token(mock_collections):
    """reset_password raises ValueError when atomic claim returns None (expired/used/invalid)."""
    from src.services.auth import AuthService

    # find_one_and_update returns None when token is expired, used, or nonexistent
    mock_collections["reset_tokens"].find_one_and_update.return_value = None

    service = AuthService(
        users_collection=mock_collections["users"],
        tenants_collection=mock_collections["tenants"],
        reset_tokens_collection=mock_collections["reset_tokens"],
    )

    with pytest.raises(ValueError, match="Invalid or expired"):
        await service.reset_password(token="any-token", new_password="newpassword123")

    # Verify no password update was attempted
    mock_collections["users"].update_one.assert_not_called()


@pytest.mark.unit
async def test_reset_password_user_not_found(mock_collections):
    """reset_password raises ValueError when token is valid but user doesn't exist."""
    from src.services.auth import AuthService

    raw_token = secrets.token_urlsafe(32)

    mock_collections["reset_tokens"].find_one_and_update.return_value = {
        "_id": "token-id",
        "user_id": MOCK_USER_OID,
        "tenant_id": "tenant-abc",
        "token_hash": hashlib.sha256(raw_token.encode()).hexdigest(),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "used": False,
    }
    # User lookup returns None — user was deleted after token was issued
    mock_collections["users"].find_one.return_value = None

    service = AuthService(
        users_collection=mock_collections["users"],
        tenants_collection=mock_collections["tenants"],
        reset_tokens_collection=mock_collections["reset_tokens"],
    )

    with pytest.raises(ValueError, match="Invalid or expired reset token"):
        await service.reset_password(token=raw_token, new_password="newpassword123")


@pytest.mark.unit
async def test_reset_token_includes_tenant_id():
    """create_password_reset_token stores tenant_id from user doc."""
    users_col = MagicMock()
    tenants_col = MagicMock()
    reset_tokens_col = MagicMock()

    users_col.find_one = AsyncMock(
        return_value={
            "_id": ObjectId(),
            "email": "alice@example.com",
            "tenant_id": "tenant-abc",
        }
    )
    reset_tokens_col.update_many = AsyncMock()
    reset_tokens_col.insert_one = AsyncMock()

    service = AuthService(users_col, tenants_col, reset_tokens_col)
    await service.create_password_reset_token("alice@example.com")

    inserted_doc = reset_tokens_col.insert_one.call_args[0][0]
    assert inserted_doc["tenant_id"] == "tenant-abc"


@pytest.mark.unit
async def test_reset_password_validates_tenant_id():
    """reset_password verifies token tenant_id matches user tenant_id."""
    users_col = MagicMock()
    tenants_col = MagicMock()
    reset_tokens_col = MagicMock()

    token_user_id = str(ObjectId())

    reset_tokens_col.find_one_and_update = AsyncMock(
        return_value={
            "user_id": token_user_id,
            "tenant_id": "tenant-abc",
            "token_hash": "abc123",
        }
    )

    # User belongs to a DIFFERENT tenant
    users_col.find_one = AsyncMock(
        return_value={
            "_id": ObjectId(token_user_id),
            "tenant_id": "tenant-xyz",
        }
    )
    users_col.update_one = AsyncMock(return_value=MagicMock(matched_count=1))

    service = AuthService(users_col, tenants_col, reset_tokens_col)
    with pytest.raises(ValueError, match="Invalid or expired reset token"):
        await service.reset_password("some-token", "new-password")


@pytest.mark.unit
async def test_reset_password_allows_legacy_token_without_tenant_id():
    """reset_password succeeds for legacy tokens missing tenant_id field."""
    users_col = MagicMock()
    tenants_col = MagicMock()
    reset_tokens_col = MagicMock()

    token_user_id = str(ObjectId())

    # Legacy token: no tenant_id field
    reset_tokens_col.find_one_and_update = AsyncMock(
        return_value={
            "user_id": token_user_id,
            "token_hash": "abc123",
        }
    )

    users_col.find_one = AsyncMock(
        return_value={
            "_id": ObjectId(token_user_id),
            "tenant_id": "tenant-abc",
        }
    )
    users_col.update_one = AsyncMock(return_value=MagicMock(matched_count=1))

    service = AuthService(users_col, tenants_col, reset_tokens_col)
    # Should NOT raise — legacy tokens without tenant_id are allowed
    await service.reset_password("some-token", "new-password")
    users_col.update_one.assert_called_once()
