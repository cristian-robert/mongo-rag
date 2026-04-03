"""Tests for auth service."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId

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
    """Signup with existing email raises ValueError."""
    from src.services.auth import AuthService

    mock_collections["users"].find_one.return_value = {"email": "test@example.com"}

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
    """reset_password updates password for valid token."""
    from src.services.auth import AuthService

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    mock_collections["reset_tokens"].find_one.return_value = {
        "_id": "token-id",
        "user_id": MOCK_USER_OID,
        "token_hash": token_hash,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "used": False,
    }

    service = AuthService(
        users_collection=mock_collections["users"],
        tenants_collection=mock_collections["tenants"],
        reset_tokens_collection=mock_collections["reset_tokens"],
    )

    await service.reset_password(token=raw_token, new_password="newpassword123")

    # Verify password was updated with ObjectId filter
    mock_collections["users"].update_one.assert_called_once()
    update_call = mock_collections["users"].update_one.call_args
    assert update_call[0][0] == {"_id": ObjectId(MOCK_USER_OID)}
    assert update_call[0][1]["$set"]["hashed_password"].startswith("$2b$")

    # Verify token was marked as used
    mock_collections["reset_tokens"].update_one.assert_called_once()


@pytest.mark.unit
async def test_reset_password_expired_token(mock_collections):
    """reset_password raises ValueError for expired token."""
    from src.services.auth import AuthService

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    mock_collections["reset_tokens"].find_one.return_value = {
        "_id": "token-id",
        "user_id": MOCK_USER_OID,
        "token_hash": token_hash,
        "expires_at": datetime.now(timezone.utc) - timedelta(hours=1),
        "used": False,
    }

    service = AuthService(
        users_collection=mock_collections["users"],
        tenants_collection=mock_collections["tenants"],
        reset_tokens_collection=mock_collections["reset_tokens"],
    )

    with pytest.raises(ValueError, match="expired"):
        await service.reset_password(token=raw_token, new_password="newpassword123")


@pytest.mark.unit
async def test_reset_password_already_used_token(mock_collections):
    """reset_password raises ValueError for already-used token."""
    from src.services.auth import AuthService

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    mock_collections["reset_tokens"].find_one.return_value = {
        "_id": "token-id",
        "user_id": MOCK_USER_OID,
        "token_hash": token_hash,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "used": True,
    }

    service = AuthService(
        users_collection=mock_collections["users"],
        tenants_collection=mock_collections["tenants"],
        reset_tokens_collection=mock_collections["reset_tokens"],
    )

    with pytest.raises(ValueError, match="already been used"):
        await service.reset_password(token=raw_token, new_password="newpassword123")


@pytest.mark.unit
async def test_reset_password_invalid_token(mock_collections):
    """reset_password raises ValueError for invalid token."""
    from src.services.auth import AuthService

    mock_collections["reset_tokens"].find_one.return_value = None

    service = AuthService(
        users_collection=mock_collections["users"],
        tenants_collection=mock_collections["tenants"],
        reset_tokens_collection=mock_collections["reset_tokens"],
    )

    with pytest.raises(ValueError, match="Invalid"):
        await service.reset_password(token="bogus-token", new_password="newpassword123")
