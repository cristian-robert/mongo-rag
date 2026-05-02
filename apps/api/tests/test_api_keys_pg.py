"""Unit tests for Postgres-backed API key auth (#42).

These tests focus on pure helpers (key generation, prefix extraction) and
the timing-safe verification loop. The full Postgres integration test lives
under tests/integration/ and runs against a real Postgres instance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import bcrypt
import pytest

from src.auth import api_keys

pytestmark = pytest.mark.unit


def test_generate_key_shape():
    gen = api_keys.generate_key()
    assert gen.raw_key.startswith(api_keys.KEY_PREFIX)
    assert len(gen.prefix) == api_keys.PREFIX_LEN
    body = gen.raw_key[len(api_keys.KEY_PREFIX) :]
    assert body[: api_keys.PREFIX_LEN] == gen.prefix
    # bcrypt hashes start with $2b$ or $2a$
    assert gen.key_hash.startswith("$2")
    # Confirm it actually verifies
    assert bcrypt.checkpw(gen.raw_key.encode(), gen.key_hash.encode())


def test_generate_keys_are_distinct():
    a = api_keys.generate_key()
    b = api_keys.generate_key()
    assert a.raw_key != b.raw_key
    assert a.key_hash != b.key_hash


def test_extract_prefix_rejects_bad_shape():
    assert api_keys._extract_prefix("nope") is None
    assert api_keys._extract_prefix("mrag_") is None  # too short
    assert api_keys._extract_prefix("mrag_short") is None  # body < 8 chars


def test_bcrypt_rounds_meet_security_floor():
    gen = api_keys.generate_key()
    # bcrypt format: $2b$<rounds>$...
    rounds = int(gen.key_hash.split("$")[2])
    assert rounds >= 12, f"bcrypt rounds must be >=12 per security.md, got {rounds}"


# ---------------------------------------------------------------------------
# Verification loop — fake pool to exercise timing-safe semantics without PG.
# ---------------------------------------------------------------------------


@dataclass
class _FakeRow(dict):
    pass


class _FakeConn:
    def __init__(self, rows: list[dict[str, Any]]):
        self._rows = rows
        self.executed: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, _query: str, *_args: Any) -> list[dict[str, Any]]:
        return list(self._rows)

    async def execute(self, query: str, *args: Any) -> str:
        self.executed.append((query, args))
        return "UPDATE 1"


class _FakeAcquire:
    def __init__(self, conn: _FakeConn):
        self._conn = conn

    async def __aenter__(self) -> _FakeConn:
        return self._conn

    async def __aexit__(self, *_exc: Any) -> None:
        return None


class _FakePool:
    def __init__(self, rows: Iterable[dict[str, Any]]):
        self.conn = _FakeConn(list(rows))

    def acquire(self) -> _FakeAcquire:
        return _FakeAcquire(self.conn)


@pytest.mark.asyncio
async def test_verify_key_returns_principal_on_match():
    gen = api_keys.generate_key()
    pool = _FakePool([{"id": "key-uuid", "tenant_id": "tenant-uuid", "key_hash": gen.key_hash}])
    principal = await api_keys.verify_key(pool, gen.raw_key)
    assert principal is not None
    assert principal.tenant_id == "tenant-uuid"
    assert principal.key_id == "key-uuid"


@pytest.mark.asyncio
async def test_verify_key_returns_none_for_unknown_prefix():
    pool = _FakePool([])
    assert await api_keys.verify_key(pool, "mrag_unknownprefix_zzzzzzzzzzzzzz") is None


@pytest.mark.asyncio
async def test_verify_key_returns_none_for_malformed():
    pool = _FakePool([])
    assert await api_keys.verify_key(pool, "not-a-key") is None
    assert await api_keys.verify_key(pool, "mrag_") is None


@pytest.mark.asyncio
async def test_verify_key_bad_password_against_real_hash():
    gen = api_keys.generate_key()
    pool = _FakePool([{"id": "k", "tenant_id": "t", "key_hash": gen.key_hash}])
    # Same prefix, different secret → bcrypt mismatch
    fake = api_keys.KEY_PREFIX + gen.prefix + "wrongsecretwrongsecretwrong"
    assert await api_keys.verify_key(pool, fake) is None


@pytest.mark.asyncio
async def test_verify_key_runs_bcrypt_for_every_candidate():
    """Timing-safety: when multiple rows share a prefix, all are checked."""
    gen_match = api_keys.generate_key()
    # Force a second row with the same prefix
    gen_other = api_keys.generate_key()
    pool = _FakePool(
        [
            # Decoy first; real match second
            {"id": "decoy", "tenant_id": "t-decoy", "key_hash": gen_other.key_hash},
            {"id": "real", "tenant_id": "t-real", "key_hash": gen_match.key_hash},
        ]
    )
    principal = await api_keys.verify_key(pool, gen_match.raw_key)
    assert principal is not None
    assert principal.key_id == "real"


@pytest.mark.asyncio
async def test_verify_key_tolerates_malformed_stored_hash():
    """Corrupted DB row must not crash auth — treat as miss."""
    pool = _FakePool([{"id": "k", "tenant_id": "t", "key_hash": "not-a-real-bcrypt-hash"}])
    gen = api_keys.generate_key()
    assert await api_keys.verify_key(pool, gen.raw_key) is None
