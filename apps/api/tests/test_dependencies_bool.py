"""Regression test: AgentDependencies must not invoke bool() on pymongo objects.

pymongo.AsyncDatabase and AsyncMongoClient deliberately raise NotImplementedError
from __bool__ (you must compare with `is None`). The accessors in
`AgentDependencies` historically used `if not self.db:` which broke every
endpoint that hit the Supabase JWT path after migration. This test pins the
fix to the public accessor surface so the regression cannot return.
"""

from unittest.mock import MagicMock

import pytest


@pytest.mark.unit
def test_get_collection_does_not_bool_check_db():
    """`_get_collection` must use `is None`, not truthy check, on `self.db`."""
    from src.core.dependencies import AgentDependencies

    deps = AgentDependencies()

    # Stub a `db` whose __bool__ raises — mirrors pymongo.AsyncDatabase.
    db_stub = MagicMock()
    db_stub.__bool__ = MagicMock(side_effect=NotImplementedError("compare with None"))
    db_stub.__getitem__ = MagicMock(return_value="<collection>")
    deps.db = db_stub

    settings_stub = MagicMock()
    settings_stub.mongodb_collection_users = "users"
    deps.settings = settings_stub

    # Must not raise NotImplementedError.
    assert deps.users_collection == "<collection>"


@pytest.mark.unit
def test_get_collection_raises_when_db_none():
    """Sanity check: when `db` is None we still raise the configured error."""
    from src.core.dependencies import AgentDependencies

    deps = AgentDependencies()
    deps.db = None
    settings_stub = MagicMock()
    settings_stub.mongodb_collection_users = "users"
    deps.settings = settings_stub

    with pytest.raises(RuntimeError, match="Dependencies not initialized"):
        _ = deps.users_collection
