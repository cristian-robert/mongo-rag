"""Team management service — members and invitations.

Authorization is enforced at the router layer. This service implements
business invariants:

* the last owner of a tenant cannot be demoted or removed;
* only owners may grant/transfer the ``owner`` role;
* invitations are tenant-scoped and stored as a SHA-256 hash;
* tokens are single-use, expire after a configured TTL, and only the
  intended email may accept.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import DuplicateKeyError

from src.core.security import hash_password
from src.models.user import UserRole

logger = logging.getLogger(__name__)


class TeamError(ValueError):
    """Domain error for team operations (mapped to 4xx by router)."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _strip_user_doc(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "email": doc["email"],
        "name": doc.get("name", ""),
        "role": doc.get("role", UserRole.MEMBER.value),
        "is_active": bool(doc.get("is_active", True)),
        "created_at": doc.get("created_at"),
    }


def _strip_invite_doc(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "email": doc["email"],
        "role": doc["role"],
        "expires_at": doc["expires_at"],
        "accepted_at": doc.get("accepted_at"),
        "revoked_at": doc.get("revoked_at"),
        "created_at": doc["created_at"],
    }


class TeamService:
    """Members + invitations, scoped by tenant_id."""

    def __init__(
        self,
        users_collection: AsyncCollection,
        tenants_collection: AsyncCollection,
        invitations_collection: AsyncCollection,
        invitation_ttl_hours: int = 168,
    ) -> None:
        self._users = users_collection
        self._tenants = tenants_collection
        self._invitations = invitations_collection
        self._ttl = timedelta(hours=invitation_ttl_hours)

    # --- Members -------------------------------------------------------

    async def list_members(self, tenant_id: str) -> list[dict[str, Any]]:
        cursor = self._users.find({"tenant_id": tenant_id}).sort("created_at", 1)
        return [_strip_user_doc(d) async for d in cursor]

    async def get_member(self, tenant_id: str, user_id: str) -> Optional[dict[str, Any]]:
        try:
            oid = ObjectId(user_id)
        except (InvalidId, TypeError):
            return None
        doc = await self._users.find_one({"_id": oid, "tenant_id": tenant_id})
        return _strip_user_doc(doc) if doc else None

    async def _count_owners(self, tenant_id: str) -> int:
        return await self._users.count_documents(
            {"tenant_id": tenant_id, "role": UserRole.OWNER.value}
        )

    async def update_member_role(
        self,
        *,
        tenant_id: str,
        target_user_id: str,
        new_role: UserRole,
        actor_user_id: str,
        actor_role: UserRole,
    ) -> Optional[dict[str, Any]]:
        try:
            oid = ObjectId(target_user_id)
        except (InvalidId, TypeError):
            return None

        target = await self._users.find_one({"_id": oid, "tenant_id": tenant_id})
        if not target:
            return None

        current_role = target.get("role", UserRole.MEMBER.value)

        # Only owners can promote anyone TO owner, or demote an owner.
        if (new_role == UserRole.OWNER or current_role == UserRole.OWNER.value) and (
            actor_role != UserRole.OWNER
        ):
            raise TeamError("Only owners can change owner roles", status_code=403)

        # Last-owner-protection: cannot demote the last owner.
        if (
            current_role == UserRole.OWNER.value
            and new_role != UserRole.OWNER
            and await self._count_owners(tenant_id) <= 1
        ):
            raise TeamError(
                "Cannot demote the last owner — promote another member first",
                status_code=409,
            )

        # No-op fast path
        if current_role == new_role.value:
            return _strip_user_doc(target)

        result = await self._users.find_one_and_update(
            {"_id": oid, "tenant_id": tenant_id, "role": current_role},
            {
                "$set": {
                    "role": new_role.value,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            return_document=True,
        )
        if not result:
            # Concurrent role change — re-evaluate.
            raise TeamError("Concurrent role change, retry", status_code=409)

        # Recheck-after-write: if the previous role was owner, confirm at
        # least one owner still remains. Defends against the race where two
        # concurrent demotions both pass the count check above.
        if current_role == UserRole.OWNER.value and new_role != UserRole.OWNER:
            if await self._count_owners(tenant_id) == 0:
                # Roll back atomically.
                await self._users.update_one(
                    {"_id": oid, "tenant_id": tenant_id},
                    {"$set": {"role": current_role}},
                )
                raise TeamError(
                    "Cannot demote the last owner — promote another member first",
                    status_code=409,
                )

        logger.info(
            "team_member_role_changed",
            extra={
                "tenant_id": tenant_id,
                "actor_user_id": actor_user_id,
                "target_user_id": target_user_id,
                "from_role": current_role,
                "to_role": new_role.value,
            },
        )
        return _strip_user_doc(result)

    async def remove_member(
        self,
        *,
        tenant_id: str,
        target_user_id: str,
        actor_user_id: str,
        actor_role: UserRole,
    ) -> bool:
        try:
            oid = ObjectId(target_user_id)
        except (InvalidId, TypeError):
            return False

        target = await self._users.find_one({"_id": oid, "tenant_id": tenant_id})
        if not target:
            return False

        target_role = target.get("role", UserRole.MEMBER.value)

        # Only owners can remove other owners.
        if target_role == UserRole.OWNER.value and actor_role != UserRole.OWNER:
            raise TeamError("Only owners can remove an owner", status_code=403)

        # Last-owner-protection.
        if (
            target_role == UserRole.OWNER.value
            and await self._count_owners(tenant_id) <= 1
        ):
            raise TeamError(
                "Cannot remove the last owner — promote another member first",
                status_code=409,
            )

        # Prevent self-removal of the only owner.
        if str(target["_id"]) == actor_user_id and target_role == UserRole.OWNER.value:
            if await self._count_owners(tenant_id) <= 1:
                raise TeamError(
                    "Cannot remove yourself as the last owner",
                    status_code=409,
                )

        result = await self._users.delete_one(
            {"_id": oid, "tenant_id": tenant_id, "role": target_role}
        )
        if result.deleted_count == 0:
            raise TeamError("Concurrent change, retry", status_code=409)

        # Recheck-after-write to close the concurrent-removal race.
        if target_role == UserRole.OWNER.value:
            if await self._count_owners(tenant_id) == 0:
                # Re-insert the owner — best effort rollback.
                await self._users.insert_one({**target})
                raise TeamError(
                    "Cannot remove the last owner — promote another member first",
                    status_code=409,
                )

        logger.info(
            "team_member_removed",
            extra={
                "tenant_id": tenant_id,
                "actor_user_id": actor_user_id,
                "target_user_id": target_user_id,
                "removed_role": target_role,
            },
        )
        return True

    # --- Invitations ---------------------------------------------------

    async def list_invitations(self, tenant_id: str) -> list[dict[str, Any]]:
        cursor = self._invitations.find({"tenant_id": tenant_id}).sort("created_at", -1)
        return [_strip_invite_doc(d) async for d in cursor]

    async def create_invitation(
        self,
        *,
        tenant_id: str,
        email: str,
        role: UserRole,
        invited_by_user_id: str,
        actor_role: UserRole,
    ) -> tuple[dict[str, Any], str]:
        """Create a pending invite. Returns (record, raw_token)."""
        if role == UserRole.OWNER and actor_role != UserRole.OWNER:
            raise TeamError("Only owners can invite another owner", status_code=403)

        email = email.strip().lower()

        existing = await self._users.find_one(
            {"tenant_id": tenant_id, "email": email}
        )
        if existing:
            raise TeamError("That email is already a member of this tenant", 409)

        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_token(raw_token)
        now = datetime.now(timezone.utc)

        doc = {
            "tenant_id": tenant_id,
            "email": email,
            "role": role.value,
            "token_hash": token_hash,
            "invited_by_user_id": invited_by_user_id,
            "expires_at": now + self._ttl,
            "accepted_at": None,
            "revoked_at": None,
            "created_at": now,
        }
        try:
            result = await self._invitations.insert_one(doc)
        except DuplicateKeyError:
            raise TeamError(
                "An invitation for that email is already pending", 409
            )

        doc["_id"] = result.inserted_id
        logger.info(
            "invitation_created",
            extra={
                "tenant_id": tenant_id,
                "invited_by_user_id": invited_by_user_id,
                "role": role.value,
            },
        )
        return _strip_invite_doc(doc), raw_token

    async def revoke_invitation(self, *, tenant_id: str, invitation_id: str) -> bool:
        try:
            oid = ObjectId(invitation_id)
        except (InvalidId, TypeError):
            return False

        result = await self._invitations.find_one_and_update(
            {
                "_id": oid,
                "tenant_id": tenant_id,
                "accepted_at": None,
                "revoked_at": None,
            },
            {"$set": {"revoked_at": datetime.now(timezone.utc)}},
        )
        return result is not None

    async def preview_invitation(self, raw_token: str) -> Optional[dict[str, Any]]:
        """Public: look up an invite by token + check whether signup is needed."""
        token_hash = _hash_token(raw_token)
        invite = await self._invitations.find_one(
            {
                "token_hash": token_hash,
                "accepted_at": None,
                "revoked_at": None,
                "expires_at": {"$gt": datetime.now(timezone.utc)},
            }
        )
        if not invite:
            return None

        tenant = await self._tenants.find_one({"tenant_id": invite["tenant_id"]})
        existing_user = await self._users.find_one({"email": invite["email"]})

        return {
            "email": invite["email"],
            "role": invite["role"],
            "organization_name": (tenant or {}).get("name", ""),
            "expires_at": invite["expires_at"],
            "requires_signup": existing_user is None,
        }

    async def accept_invitation_existing_user(
        self,
        *,
        raw_token: str,
        acting_user_id: str,
        acting_email: str,
    ) -> dict[str, Any]:
        """Accept an invite for an already-signed-in user.

        The user's tenant_id is migrated to the inviting tenant. We require
        the acting user's email to match the invite email, defending against
        token theft + cross-account replay.
        """
        invite = await self._claim_invite(raw_token)
        if invite["email"] != acting_email.strip().lower():
            # Re-open: do not consume someone else's invite.
            await self._invitations.update_one(
                {"_id": invite["_id"]},
                {"$set": {"accepted_at": None}},
            )
            raise TeamError("This invitation was issued to a different email", 403)

        try:
            user_oid = ObjectId(acting_user_id)
        except (InvalidId, TypeError):
            raise TeamError("Invalid user", 400)

        await self._users.update_one(
            {"_id": user_oid},
            {
                "$set": {
                    "tenant_id": invite["tenant_id"],
                    "role": invite["role"],
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        return {
            "user_id": acting_user_id,
            "tenant_id": invite["tenant_id"],
            "role": invite["role"],
        }

    async def accept_invitation_new_user(
        self,
        *,
        raw_token: str,
        password: str,
        name: str,
    ) -> dict[str, Any]:
        """Sign up + accept an invite atomically (no tenant created)."""
        invite = await self._claim_invite(raw_token)

        existing = await self._users.find_one({"email": invite["email"]})
        if existing:
            # Re-open the invite — caller should sign in and accept instead.
            await self._invitations.update_one(
                {"_id": invite["_id"]},
                {"$set": {"accepted_at": None}},
            )
            raise TeamError(
                "An account already exists for this email — sign in to accept",
                status_code=409,
            )

        now = datetime.now(timezone.utc)
        user_doc = {
            "tenant_id": invite["tenant_id"],
            "email": invite["email"],
            "hashed_password": hash_password(password),
            "name": name or "",
            "role": invite["role"],
            "is_active": True,
            "email_verified": True,  # email proven by accepting the invite
            "created_at": now,
            "updated_at": now,
        }
        try:
            result = await self._users.insert_one(user_doc)
        except DuplicateKeyError:
            await self._invitations.update_one(
                {"_id": invite["_id"]},
                {"$set": {"accepted_at": None}},
            )
            raise TeamError(
                "An account already exists for this email — sign in to accept",
                status_code=409,
            )

        return {
            "user_id": str(result.inserted_id),
            "tenant_id": invite["tenant_id"],
            "email": invite["email"],
            "role": invite["role"],
        }

    async def _claim_invite(self, raw_token: str) -> dict[str, Any]:
        """Atomically mark an invite accepted. Returns the original doc."""
        token_hash = _hash_token(raw_token)
        now = datetime.now(timezone.utc)

        invite = await self._invitations.find_one_and_update(
            {
                "token_hash": token_hash,
                "accepted_at": None,
                "revoked_at": None,
                "expires_at": {"$gt": now},
            },
            {"$set": {"accepted_at": now}},
        )
        if not invite:
            raise TeamError("Invalid or expired invitation", 400)
        return invite
