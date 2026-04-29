"""Shared fixtures for integration tests against a real MongoDB.

Integration tests require a reachable MongoDB instance. Set
``MONGODB_TEST_URI`` in the environment to enable; otherwise the tests
in this directory are skipped at collection time.

The test database is dropped before *and* after each test to keep
isolation explicit — never point ``MONGODB_TEST_URI`` at production data.
"""

from __future__ import annotations

import os
import uuid
from typing import AsyncIterator

import pytest

MONGODB_TEST_URI = os.environ.get("MONGODB_TEST_URI")


def _skip_if_no_mongo() -> None:
    if not MONGODB_TEST_URI:
        pytest.skip(
            "MONGODB_TEST_URI not set — integration tests require a live MongoDB",
            allow_module_level=False,
        )


@pytest.fixture
async def mongo_db() -> AsyncIterator:
    """Yield an empty, isolated test database. Drops on teardown."""
    _skip_if_no_mongo()

    try:
        from pymongo import AsyncMongoClient
    except ImportError as exc:  # pragma: no cover - depends on pymongo version
        pytest.skip(f"pymongo async client unavailable: {exc}")

    db_name = f"mongorag_it_{uuid.uuid4().hex[:8]}"
    client = AsyncMongoClient(MONGODB_TEST_URI)
    db = client[db_name]
    try:
        yield db
    finally:
        await client.drop_database(db_name)
        await client.close()
