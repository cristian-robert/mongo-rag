"""Postgres ``public.profiles`` lookup used during Supabase JWT auth.

``profiles`` is the authoritative join table between ``auth.users.id`` (the
JWT ``sub``) and a tenant. The ``handle_new_user`` trigger populates it
synchronously on signup, so a missing profile means the caller is not
provisioned (401, not 404) — there is no Mongo fallback in the new world.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProfileRow:
    """A row from ``public.profiles`` resolved from a Supabase JWT ``sub``."""

    id: str  # auth.users.id, stringified uuid
    tenant_id: str
    email: str
    role: str


async def lookup_profile(pool: asyncpg.Pool, sub: str) -> Optional[ProfileRow]:
    """Look up a profile by Supabase user id (JWT ``sub``).

    Returns ``None`` when no profile exists — let the caller decide between
    401 vs. silent ignore. A malformed ``sub`` (not a uuid) is treated the
    same way: "no such user", so callers don't need to special-case it.
    """
    try:
        sub_uuid = uuid.UUID(sub)
    except (ValueError, TypeError, AttributeError):
        return None

    row = await pool.fetchrow(
        """
        select id::text as id,
               tenant_id::text as tenant_id,
               email::text as email,
               role::text as role
          from public.profiles
         where id = $1
        """,
        sub_uuid,
    )
    if row is None:
        return None
    return ProfileRow(
        id=row["id"],
        tenant_id=row["tenant_id"],
        email=row["email"],
        role=row["role"],
    )
