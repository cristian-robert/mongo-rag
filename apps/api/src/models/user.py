"""User and API key models."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    """User roles within a tenant."""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class UserModel(BaseModel):
    """A user belonging to a tenant."""

    tenant_id: str = Field(..., description="Tenant this user belongs to")
    email: EmailStr = Field(..., description="User email address")
    hashed_password: str = Field(..., description="Bcrypt-hashed password")
    name: str = Field(default="", description="Display name")
    role: UserRole = Field(default=UserRole.MEMBER, description="Role within tenant")
    is_active: bool = Field(default=True, description="Whether the account is active")
    email_verified: bool = Field(default=False, description="Whether email has been verified")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApiKeyModel(BaseModel):
    """An API key for programmatic access."""

    tenant_id: str = Field(..., description="Tenant this key belongs to")
    key_hash: str = Field(..., description="SHA256 hash of the API key")
    key_prefix: str = Field(..., description="First 8 chars of key for identification")
    name: str = Field(..., description="Human-readable key name")
    permissions: list[str] = Field(
        default_factory=lambda: ["chat", "search"],
        description="Allowed operations",
    )
    is_revoked: bool = Field(default=False, description="Whether the key has been revoked")
    last_used_at: Optional[datetime] = Field(default=None, description="Last usage timestamp")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PasswordResetTokenModel(BaseModel):
    """A password reset token (stored as SHA256 hash)."""

    user_id: str = Field(..., description="User this token belongs to")
    tenant_id: str = Field(..., description="Tenant this token belongs to")
    token_hash: str = Field(..., description="SHA256 hash of the reset token")
    expires_at: datetime = Field(..., description="Token expiry time")
    used: bool = Field(default=False, description="Whether the token has been consumed")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
