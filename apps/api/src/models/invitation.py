"""Team invitation model."""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from src.models.user import UserRole


class InvitationModel(BaseModel):
    """A pending invitation for someone to join a tenant.

    The raw token is shown to the inviter exactly once (in the accept link).
    Only the SHA-256 hash is persisted, so a leaked DB cannot be replayed.
    """

    tenant_id: str = Field(..., description="Tenant the invitee will join")
    email: EmailStr = Field(..., description="Invitee email address")
    role: UserRole = Field(..., description="Role granted on accept")
    token_hash: str = Field(..., description="SHA-256 of the invite token")
    invited_by_user_id: str = Field(..., description="User id of inviter")
    expires_at: datetime = Field(..., description="Invitation expiry time (UTC)")
    accepted_at: Optional[datetime] = Field(
        default=None, description="When the invite was accepted"
    )
    revoked_at: Optional[datetime] = Field(default=None, description="When the invite was revoked")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
