"""Security utilities: password hashing and JWT decoding."""

import logging
from typing import Any, Optional

import bcrypt
from jose import JWTError, jwt

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt.

    Args:
        password: Plaintext password.

    Returns:
        Bcrypt hash string.
    """
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash.

    Args:
        password: Plaintext password to check.
        hashed: Bcrypt hash to verify against.

    Returns:
        True if password matches, False otherwise.
    """
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def decode_jwt(
    token: str, secret: str, algorithms: list[str] | None = None
) -> Optional[dict[str, Any]]:
    """Decode and verify a JWT token.

    Args:
        token: JWT token string.
        secret: Secret key used to sign the token.
        algorithms: Allowed algorithms (default: HS256).

    Returns:
        Decoded payload dict, or None if token is invalid.
    """
    if algorithms is None:
        algorithms = ["HS256"]
    try:
        return jwt.decode(token, secret, algorithms=algorithms)
    except JWTError:
        logger.debug("JWT decode failed", exc_info=True)
        return None
