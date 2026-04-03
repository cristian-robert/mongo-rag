"""Authentication service: signup, login, password reset."""

import hashlib
import logging
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from pymongo.asynchronous.collection import AsyncCollection

from src.core.security import hash_password, verify_password

logger = logging.getLogger(__name__)


def _slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


class AuthService:
    """Handles user signup, login, and password reset."""

    def __init__(
        self,
        users_collection: AsyncCollection,
        tenants_collection: AsyncCollection,
        reset_tokens_collection: AsyncCollection,
    ) -> None:
        self._users = users_collection
        self._tenants = tenants_collection
        self._reset_tokens = reset_tokens_collection

    async def signup(
        self, email: str, password: str, organization_name: str
    ) -> dict[str, Any]:
        """Create a new tenant and user.

        Args:
            email: User email.
            password: Plaintext password.
            organization_name: Name for the new tenant.

        Returns:
            Dict with user_id, tenant_id, email.

        Raises:
            ValueError: If email is already registered.
        """
        existing = await self._users.find_one({"email": email.lower()})
        if existing:
            raise ValueError("Email is already registered")

        now = datetime.now(timezone.utc)
        tenant_id = str(uuid.uuid4())

        tenant_doc = {
            "tenant_id": tenant_id,
            "name": organization_name,
            "slug": _slugify(organization_name),
            "plan": "free",
            "settings": {
                "max_documents": 10,
                "max_chunks": 1000,
                "max_queries_per_day": 100,
                "custom_system_prompt": None,
                "allowed_origins": [],
            },
            "created_at": now,
            "updated_at": now,
        }
        await self._tenants.insert_one(tenant_doc)

        hashed = hash_password(password)
        user_doc = {
            "tenant_id": tenant_id,
            "email": email.lower(),
            "hashed_password": hashed,
            "name": "",
            "role": "owner",
            "is_active": True,
            "email_verified": False,
            "created_at": now,
            "updated_at": now,
        }
        user_result = await self._users.insert_one(user_doc)

        logger.info(
            "user_signed_up",
            extra={"email": email, "tenant_id": tenant_id},
        )

        return {
            "user_id": str(user_result.inserted_id),
            "tenant_id": tenant_id,
            "email": email.lower(),
        }

    async def login(self, email: str, password: str) -> dict[str, Any]:
        """Validate credentials and return user data.

        Args:
            email: User email.
            password: Plaintext password.

        Returns:
            Dict with user_id, tenant_id, email, name, role.

        Raises:
            ValueError: If credentials are invalid or account is deactivated.
        """
        user = await self._users.find_one({"email": email.lower()})
        if not user:
            raise ValueError("Invalid email or password")

        if not user.get("is_active", True):
            raise ValueError("Account is deactivated")

        if not verify_password(password, user["hashed_password"]):
            raise ValueError("Invalid email or password")

        logger.info("user_logged_in", extra={"email": email})

        return {
            "user_id": str(user["_id"]),
            "tenant_id": user["tenant_id"],
            "email": user["email"],
            "name": user.get("name", ""),
            "role": user["role"],
        }

    async def create_password_reset_token(self, email: str) -> Optional[str]:
        """Generate a password reset token for the given email.

        Returns None if the email is not found (prevents email enumeration).

        Args:
            email: User email.

        Returns:
            Raw token string, or None if email not found.
        """
        user = await self._users.find_one({"email": email.lower()})
        if not user:
            return None

        user_id = str(user["_id"])

        # Invalidate any existing tokens for this user
        await self._reset_tokens.update_many(
            {"user_id": user_id, "used": False},
            {"$set": {"used": True}},
        )

        # Generate new token
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        now = datetime.now(timezone.utc)

        token_doc = {
            "user_id": user_id,
            "token_hash": token_hash,
            "expires_at": now + timedelta(hours=1),
            "used": False,
            "created_at": now,
        }
        await self._reset_tokens.insert_one(token_doc)

        logger.info("password_reset_token_created", extra={"user_id": user_id})
        return raw_token

    async def reset_password(self, token: str, new_password: str) -> None:
        """Reset a user's password using a reset token.

        Args:
            token: Raw reset token from the email link.
            new_password: New plaintext password.

        Raises:
            ValueError: If token is invalid, expired, or already used.
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        token_doc = await self._reset_tokens.find_one({"token_hash": token_hash})

        if not token_doc:
            raise ValueError("Invalid or expired reset token")

        if token_doc.get("used"):
            raise ValueError("Reset token has already been used")

        if token_doc["expires_at"] < datetime.now(timezone.utc):
            raise ValueError("Reset token has expired")

        # Update the user's password
        new_hash = hash_password(new_password)
        await self._users.update_one(
            {"_id": token_doc["user_id"]},
            {"$set": {"hashed_password": new_hash, "updated_at": datetime.now(timezone.utc)}},
        )

        # Mark token as used
        await self._reset_tokens.update_one(
            {"_id": token_doc["_id"]},
            {"$set": {"used": True}},
        )

        logger.info("password_reset_completed", extra={"user_id": token_doc["user_id"]})
