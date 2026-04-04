"""Tests for database index creation."""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.unit
async def test_ensure_indexes_creates_expected_indexes():
    """ensure_indexes creates all required indexes on startup."""
    from src.core.database import ensure_indexes

    mock_db = MagicMock()
    collections = {}
    for name in [
        "users",
        "documents",
        "chunks",
        "conversations",
        "api_keys",
        "password_reset_tokens",
    ]:
        mock_col = MagicMock()
        mock_col.create_index = AsyncMock()
        collections[name] = mock_col

    mock_db.__getitem__ = MagicMock(side_effect=lambda name: collections[name])

    await ensure_indexes(mock_db)

    # users: unique email index
    collections["users"].create_index.assert_any_call("email", unique=True, background=True)

    # documents: tenant + created_at compound
    collections["documents"].create_index.assert_any_call(
        [("tenant_id", 1), ("created_at", -1)], background=True
    )

    # chunks: tenant + document_id compound
    collections["chunks"].create_index.assert_any_call(
        [("tenant_id", 1), ("document_id", 1)], background=True
    )

    # conversations: tenant + created_at compound
    collections["conversations"].create_index.assert_any_call(
        [("tenant_id", 1), ("created_at", -1)], background=True
    )

    # api_keys: tenant_id
    collections["api_keys"].create_index.assert_any_call("tenant_id", background=True)

    # reset_tokens: token_hash
    collections["password_reset_tokens"].create_index.assert_any_call("token_hash", background=True)

    # reset_tokens: TTL on expires_at (24 hours)
    collections["password_reset_tokens"].create_index.assert_any_call(
        "expires_at", expireAfterSeconds=86400, background=True
    )
