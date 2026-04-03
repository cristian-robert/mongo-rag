"""Tests for security utilities (password hashing, JWT decode)."""

import pytest


@pytest.mark.unit
def test_hash_password_returns_bcrypt_hash():
    """hash_password returns a bcrypt hash string."""
    from src.core.security import hash_password

    hashed = hash_password("mypassword123")
    assert hashed.startswith("$2b$")
    assert len(hashed) == 60


@pytest.mark.unit
def test_verify_password_correct():
    """verify_password returns True for correct password."""
    from src.core.security import hash_password, verify_password

    hashed = hash_password("mypassword123")
    assert verify_password("mypassword123", hashed) is True


@pytest.mark.unit
def test_verify_password_incorrect():
    """verify_password returns False for wrong password."""
    from src.core.security import hash_password, verify_password

    hashed = hash_password("mypassword123")
    assert verify_password("wrongpassword", hashed) is False


@pytest.mark.unit
def test_decode_jwt_valid_token():
    """decode_jwt successfully decodes a valid JWT."""
    from jose import jwt

    from src.core.security import decode_jwt

    secret = "test-secret-for-jwt-minimum-32-characters"
    payload = {"sub": "user123", "tenant_id": "tenant-abc", "role": "owner"}
    token = jwt.encode(payload, secret, algorithm="HS256")

    decoded = decode_jwt(token, secret)
    assert decoded["sub"] == "user123"
    assert decoded["tenant_id"] == "tenant-abc"
    assert decoded["role"] == "owner"


@pytest.mark.unit
def test_decode_jwt_invalid_token():
    """decode_jwt returns None for invalid token."""
    from src.core.security import decode_jwt

    result = decode_jwt("invalid.token.here", "secret")
    assert result is None


@pytest.mark.unit
def test_decode_jwt_wrong_secret():
    """decode_jwt returns None when signed with different secret."""
    from jose import jwt

    from src.core.security import decode_jwt

    token = jwt.encode({"sub": "user123"}, "correct-secret-32-chars-minimum!!", algorithm="HS256")
    result = decode_jwt(token, "wrong-secret-32-chars-minimum!!!")
    assert result is None
