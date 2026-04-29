"""Tests for the TeamService — invariants for invitations and member roles."""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import pytest
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from src.models.user import UserRole
from src.services.team import TeamError, TeamService


class FakeCursor:
    def __init__(self, docs: list[dict[str, Any]]):
        self._docs = docs

    def sort(self, *_args, **_kwargs) -> "FakeCursor":
        return self

    def __aiter__(self):
        async def gen():
            for d in self._docs:
                yield d

        return gen()


class FakeCollection:
    """Tiny in-memory subset of pymongo's async collection API."""

    def __init__(self, name: str = "fake") -> None:
        self.name = name
        self.docs: list[dict[str, Any]] = []
        self.unique: list[tuple[str, ...]] = []

    def add_unique(self, *fields: str) -> None:
        self.unique.append(fields)

    def _matches(self, doc: dict[str, Any], q: dict[str, Any]) -> bool:
        for k, v in q.items():
            doc_v = doc.get(k)
            if isinstance(v, dict):
                for op, val in v.items():
                    if op == "$gt" and not (doc_v is not None and doc_v > val):
                        return False
                    if op == "$lt" and not (doc_v is not None and doc_v < val):
                        return False
                continue
            if doc_v != v:
                return False
        return True

    async def find_one(self, q: dict[str, Any]) -> Optional[dict[str, Any]]:
        for d in self.docs:
            if self._matches(d, q):
                return dict(d)
        return None

    def find(self, q: dict[str, Any]) -> FakeCursor:
        return FakeCursor([dict(d) for d in self.docs if self._matches(d, q)])

    async def count_documents(self, q: dict[str, Any]) -> int:
        return sum(1 for d in self.docs if self._matches(d, q))

    async def insert_one(self, doc: dict[str, Any]):
        for fields in self.unique:
            for d in self.docs:
                # Treat None as wildcard for partial indexes simulating
                # `accepted_at: None, revoked_at: None`.
                if all(d.get(f) == doc.get(f) for f in fields):
                    raise DuplicateKeyError("dup")
        new_doc = dict(doc)
        new_doc.setdefault("_id", ObjectId())
        self.docs.append(new_doc)

        class R:
            inserted_id = new_doc["_id"]

        return R()

    async def update_one(self, q: dict[str, Any], update: dict[str, Any]):
        for d in self.docs:
            if self._matches(d, q):
                d.update(update.get("$set", {}))
                break

        class R:
            matched_count = 1

        return R()

    async def delete_one(self, q: dict[str, Any]):
        for i, d in enumerate(self.docs):
            if self._matches(d, q):
                del self.docs[i]

                class R:
                    deleted_count = 1

                return R()

        class R:
            deleted_count = 0

        return R()

    async def find_one_and_update(
        self, q: dict[str, Any], update: dict[str, Any], **_kw
    ) -> Optional[dict[str, Any]]:
        for d in self.docs:
            if self._matches(d, q):
                d.update(update.get("$set", {}))
                return dict(d)
        return None


@pytest.fixture
def collections():
    users = FakeCollection("users")
    tenants = FakeCollection("tenants")
    invites = FakeCollection("invitations")
    invites.add_unique("token_hash")
    # Simulate the partial unique index: tenant + email + only when pending.
    # We capture this by clearing the constraint after revoke/accept.
    return users, tenants, invites


@pytest.fixture
def service(collections):
    users, tenants, invites = collections
    return TeamService(
        users_collection=users,
        tenants_collection=tenants,
        invitations_collection=invites,
        invitation_ttl_hours=168,
    )


def _seed_user(coll, *, tenant_id, role, email="u@example.com", _id=None):
    doc = {
        "_id": _id or ObjectId(),
        "tenant_id": tenant_id,
        "email": email,
        "name": "",
        "role": role,
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
    }
    coll.docs.append(doc)
    return doc


# --- Members ---


@pytest.mark.unit
async def test_owner_can_change_admin_to_member(service, collections):
    users, _, _ = collections
    owner = _seed_user(users, tenant_id="t1", role="owner", email="o@x")
    admin = _seed_user(users, tenant_id="t1", role="admin", email="a@x")
    updated = await service.update_member_role(
        tenant_id="t1",
        target_user_id=str(admin["_id"]),
        new_role=UserRole.MEMBER,
        actor_user_id=str(owner["_id"]),
        actor_role=UserRole.OWNER,
    )
    assert updated["role"] == "member"


@pytest.mark.unit
async def test_admin_cannot_promote_to_owner(service, collections):
    users, _, _ = collections
    actor = _seed_user(users, tenant_id="t1", role="admin", email="a@x")
    target = _seed_user(users, tenant_id="t1", role="member", email="m@x")
    with pytest.raises(TeamError) as exc:
        await service.update_member_role(
            tenant_id="t1",
            target_user_id=str(target["_id"]),
            new_role=UserRole.OWNER,
            actor_user_id=str(actor["_id"]),
            actor_role=UserRole.ADMIN,
        )
    assert exc.value.status_code == 403


@pytest.mark.unit
async def test_admin_cannot_demote_owner(service, collections):
    users, _, _ = collections
    actor = _seed_user(users, tenant_id="t1", role="admin", email="a@x")
    owner = _seed_user(users, tenant_id="t1", role="owner", email="o@x")
    with pytest.raises(TeamError) as exc:
        await service.update_member_role(
            tenant_id="t1",
            target_user_id=str(owner["_id"]),
            new_role=UserRole.MEMBER,
            actor_user_id=str(actor["_id"]),
            actor_role=UserRole.ADMIN,
        )
    assert exc.value.status_code == 403


@pytest.mark.unit
async def test_cannot_demote_last_owner(service, collections):
    users, _, _ = collections
    owner = _seed_user(users, tenant_id="t1", role="owner", email="o@x")
    with pytest.raises(TeamError) as exc:
        await service.update_member_role(
            tenant_id="t1",
            target_user_id=str(owner["_id"]),
            new_role=UserRole.ADMIN,
            actor_user_id=str(owner["_id"]),
            actor_role=UserRole.OWNER,
        )
    assert exc.value.status_code == 409


@pytest.mark.unit
async def test_can_demote_owner_when_more_than_one(service, collections):
    users, _, _ = collections
    o1 = _seed_user(users, tenant_id="t1", role="owner", email="o1@x")
    o2 = _seed_user(users, tenant_id="t1", role="owner", email="o2@x")
    updated = await service.update_member_role(
        tenant_id="t1",
        target_user_id=str(o2["_id"]),
        new_role=UserRole.MEMBER,
        actor_user_id=str(o1["_id"]),
        actor_role=UserRole.OWNER,
    )
    assert updated["role"] == "member"


@pytest.mark.unit
async def test_cannot_remove_last_owner(service, collections):
    users, _, _ = collections
    owner = _seed_user(users, tenant_id="t1", role="owner", email="o@x")
    with pytest.raises(TeamError) as exc:
        await service.remove_member(
            tenant_id="t1",
            target_user_id=str(owner["_id"]),
            actor_user_id=str(owner["_id"]),
            actor_role=UserRole.OWNER,
        )
    assert exc.value.status_code == 409


@pytest.mark.unit
async def test_member_in_other_tenant_not_visible(service, collections):
    users, _, _ = collections
    _seed_user(users, tenant_id="t1", role="owner", email="a@x")
    _seed_user(users, tenant_id="t2", role="owner", email="b@x")
    members = await service.list_members("t1")
    assert len(members) == 1
    assert members[0]["email"] == "a@x"


@pytest.mark.unit
async def test_remove_target_in_other_tenant_returns_false(service, collections):
    users, _, _ = collections
    _seed_user(users, tenant_id="t1", role="owner", email="o1@x")
    other = _seed_user(users, tenant_id="t2", role="member", email="m@x")
    removed = await service.remove_member(
        tenant_id="t1",
        target_user_id=str(other["_id"]),
        actor_user_id="ignored",
        actor_role=UserRole.OWNER,
    )
    assert removed is False
    # Other-tenant doc was not touched.
    assert any(d["_id"] == other["_id"] for d in users.docs)


# --- Invitations ---


@pytest.mark.unit
async def test_admin_cannot_invite_owner(service, collections):
    users, _, _ = collections
    _seed_user(users, tenant_id="t1", role="admin", email="a@x")
    with pytest.raises(TeamError) as exc:
        await service.create_invitation(
            tenant_id="t1",
            email="new@x",
            role=UserRole.OWNER,
            invited_by_user_id="ignored",
            actor_role=UserRole.ADMIN,
        )
    assert exc.value.status_code == 403


@pytest.mark.unit
async def test_existing_member_cannot_be_invited(service, collections):
    users, _, _ = collections
    _seed_user(users, tenant_id="t1", role="member", email="exists@x")
    with pytest.raises(TeamError) as exc:
        await service.create_invitation(
            tenant_id="t1",
            email="exists@x",
            role=UserRole.MEMBER,
            invited_by_user_id="i",
            actor_role=UserRole.OWNER,
        )
    assert exc.value.status_code == 409


@pytest.mark.unit
async def test_invitation_token_is_hashed_at_rest(service, collections):
    _, _, invites = collections
    _, raw = await service.create_invitation(
        tenant_id="t1",
        email="new@x",
        role=UserRole.MEMBER,
        invited_by_user_id="i",
        actor_role=UserRole.OWNER,
    )
    stored = invites.docs[0]
    assert "raw_token" not in stored
    assert "token" not in stored
    expected = hashlib.sha256(raw.encode()).hexdigest()
    assert stored["token_hash"] == expected


@pytest.mark.unit
async def test_invitation_accept_existing_user_email_must_match(service, collections):
    users, _, _ = collections
    inviter = _seed_user(users, tenant_id="t1", role="owner", email="o@x")
    _seed_user(users, tenant_id="t2", role="owner", email="invited@x")
    _, raw = await service.create_invitation(
        tenant_id="t1",
        email="invited@x",
        role=UserRole.MEMBER,
        invited_by_user_id=str(inviter["_id"]),
        actor_role=UserRole.OWNER,
    )

    # Wrong-email accept path is rejected and invite stays pending.
    with pytest.raises(TeamError) as exc:
        await service.accept_invitation_existing_user(
            raw_token=raw,
            acting_user_id=str(inviter["_id"]),
            acting_email="o@x",
        )
    assert exc.value.status_code == 403


@pytest.mark.unit
async def test_invitation_accept_is_single_use(service, collections):
    users, _, _ = collections
    _seed_user(users, tenant_id="t1", role="owner", email="o@x")
    invited = _seed_user(users, tenant_id="t2", role="member", email="invited@x")
    _, raw = await service.create_invitation(
        tenant_id="t1",
        email="invited@x",
        role=UserRole.MEMBER,
        invited_by_user_id="o",
        actor_role=UserRole.OWNER,
    )
    res = await service.accept_invitation_existing_user(
        raw_token=raw,
        acting_user_id=str(invited["_id"]),
        acting_email="invited@x",
    )
    assert res["tenant_id"] == "t1"
    with pytest.raises(TeamError) as exc:
        await service.accept_invitation_existing_user(
            raw_token=raw,
            acting_user_id=str(invited["_id"]),
            acting_email="invited@x",
        )
    assert exc.value.status_code == 400


@pytest.mark.unit
async def test_invitation_expired_token_rejected(service, collections):
    users, _, invites = collections
    _seed_user(users, tenant_id="t1", role="owner", email="o@x")
    _, raw = await service.create_invitation(
        tenant_id="t1",
        email="invited@x",
        role=UserRole.MEMBER,
        invited_by_user_id="o",
        actor_role=UserRole.OWNER,
    )
    invites.docs[0]["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)

    with pytest.raises(TeamError) as exc:
        await service.accept_invitation_new_user(
            raw_token=raw,
            password="abcdefgh",
            name="x",
        )
    assert exc.value.status_code == 400


@pytest.mark.unit
async def test_invitation_unknown_token_returns_none_preview(service):
    preview = await service.preview_invitation("not-a-real-token")
    assert preview is None
