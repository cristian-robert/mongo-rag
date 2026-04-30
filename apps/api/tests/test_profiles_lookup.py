"""Unit tests for ``src.auth.profiles.lookup_profile``."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.auth.profiles import lookup_profile

VALID_SUB = "11111111-1111-1111-1111-111111111111"
VALID_TENANT = "22222222-2222-2222-2222-222222222222"


@pytest.mark.unit
async def test_lookup_profile_returns_row_when_found():
    pool = MagicMock()
    pool.fetchrow = AsyncMock(
        return_value={
            "id": VALID_SUB,
            "tenant_id": VALID_TENANT,
            "email": "u@example.com",
            "role": "owner",
        }
    )

    profile = await lookup_profile(pool, VALID_SUB)

    assert profile is not None
    assert profile.id == VALID_SUB
    assert profile.tenant_id == VALID_TENANT
    assert profile.email == "u@example.com"
    assert profile.role == "owner"
    pool.fetchrow.assert_awaited_once()


@pytest.mark.unit
async def test_lookup_profile_returns_none_when_missing():
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=None)

    profile = await lookup_profile(pool, VALID_SUB)

    assert profile is None
    pool.fetchrow.assert_awaited_once()


@pytest.mark.unit
async def test_lookup_profile_returns_none_for_invalid_uuid():
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=None)

    profile = await lookup_profile(pool, "not-a-uuid")

    assert profile is None
    # Don't even hit the DB for a malformed sub.
    pool.fetchrow.assert_not_called()


@pytest.mark.unit
async def test_lookup_profile_returns_none_for_empty_sub():
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=None)

    profile = await lookup_profile(pool, "")

    assert profile is None
    pool.fetchrow.assert_not_called()
