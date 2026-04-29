"""Unit tests for the MongoDB migration runner.

Uses an in-memory ``mongomock_motor``-style fake. We avoid extra deps by
implementing a tiny async stand-in that supports just the surface the
runner uses: ``find``, ``insert_one``, ``delete_one``, ``sort``.
"""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass, field
from typing import Any

import pytest

from src.migrations import runner

# ---------- minimal async-compatible mongo fake ----------


class _FakeCursor:
    def __init__(self, docs: list[dict]):
        self._docs = list(docs)

    def sort(self, key: str, direction: int = 1) -> "_FakeCursor":
        self._docs.sort(key=lambda d: d.get(key), reverse=direction == -1)
        return self

    def __aiter__(self):
        self._idx = 0
        return self

    async def __anext__(self):
        if self._idx >= len(self._docs):
            raise StopAsyncIteration
        doc = self._docs[self._idx]
        self._idx += 1
        return doc


@dataclass
class _FakeCollection:
    name: str
    docs: list[dict] = field(default_factory=list)
    indexes: list[tuple] = field(default_factory=list)

    def find(self, query: dict | None = None, projection: dict | None = None) -> _FakeCursor:
        # We ignore projection since runner only reads "version".
        return _FakeCursor(list(self.docs))

    async def insert_one(self, doc: dict) -> Any:
        self.docs.append(dict(doc))

    async def delete_one(self, query: dict) -> Any:
        for i, d in enumerate(self.docs):
            if all(d.get(k) == v for k, v in query.items()):
                self.docs.pop(i)
                return
        return None

    async def create_index(self, keys, name: str | None = None, **opts) -> str:
        self.indexes.append((tuple(keys), name, opts))
        return name or "idx"

    async def drop_index(self, name: str) -> None:
        self.indexes = [i for i in self.indexes if i[1] != name]


class _FakeDB:
    def __init__(self) -> None:
        self._collections: dict[str, _FakeCollection] = {}

    def __getitem__(self, name: str) -> _FakeCollection:
        if name not in self._collections:
            self._collections[name] = _FakeCollection(name=name)
        return self._collections[name]


# ---------- helpers ----------


def _install_fake_versions(monkeypatch, modules: dict[str, dict]):
    """Inject fake migration modules under apps.api.migrations.versions."""
    pkg_name = "src.migrations.versions_test"
    pkg = types.ModuleType(pkg_name)
    pkg.__path__ = []  # mark as package; pkgutil.iter_modules returns []
    sys.modules[pkg_name] = pkg

    # We bypass discovery by monkeypatching discover_migrations directly.
    migrations: list[runner.Migration] = []
    for filename, body in modules.items():
        m = runner.Migration(
            version=body["VERSION"],
            name=body["NAME"],
            up=body["up"],
            down=body["down"],
        )
        migrations.append(m)
    migrations.sort(key=lambda m: m.version)
    monkeypatch.setattr(
        runner,
        "discover_migrations",
        lambda package="src.migrations.versions": migrations,
    )


# ---------- tests ----------


@pytest.mark.asyncio
async def test_up_applies_in_order_and_records(monkeypatch):
    applied_calls: list[str] = []

    async def up_a(db):
        applied_calls.append("a")

    async def down_a(db):
        applied_calls.append("-a")

    async def up_b(db):
        applied_calls.append("b")

    async def down_b(db):
        applied_calls.append("-b")

    _install_fake_versions(
        monkeypatch,
        {
            "0001_a": {"VERSION": "0001", "NAME": "a", "up": up_a, "down": down_a},
            "0002_b": {"VERSION": "0002", "NAME": "b", "up": up_b, "down": down_b},
        },
    )

    db = _FakeDB()
    applied = await runner.up(db)

    assert applied == ["0001_a", "0002_b"]
    assert applied_calls == ["a", "b"]
    versions = {d["version"] for d in db[runner.MIGRATIONS_COLLECTION].docs}
    assert versions == {"0001", "0002"}


@pytest.mark.asyncio
async def test_up_is_idempotent(monkeypatch):
    counter = {"a": 0}

    async def up_a(db):
        counter["a"] += 1

    async def down_a(db):
        pass

    _install_fake_versions(
        monkeypatch,
        {"0001_a": {"VERSION": "0001", "NAME": "a", "up": up_a, "down": down_a}},
    )

    db = _FakeDB()
    await runner.up(db)
    await runner.up(db)
    await runner.up(db)
    assert counter["a"] == 1


@pytest.mark.asyncio
async def test_up_target_stops(monkeypatch):
    async def noop(db):
        pass

    _install_fake_versions(
        monkeypatch,
        {
            "0001_a": {"VERSION": "0001", "NAME": "a", "up": noop, "down": noop},
            "0002_b": {"VERSION": "0002", "NAME": "b", "up": noop, "down": noop},
            "0003_c": {"VERSION": "0003", "NAME": "c", "up": noop, "down": noop},
        },
    )

    db = _FakeDB()
    applied = await runner.up(db, target="0002")
    assert applied == ["0001_a", "0002_b"]
    assert {d["version"] for d in db[runner.MIGRATIONS_COLLECTION].docs} == {"0001", "0002"}


@pytest.mark.asyncio
async def test_down_reverts_last(monkeypatch):
    log: list[str] = []

    async def up_a(db):
        log.append("up-a")

    async def down_a(db):
        log.append("down-a")

    async def up_b(db):
        log.append("up-b")

    async def down_b(db):
        log.append("down-b")

    _install_fake_versions(
        monkeypatch,
        {
            "0001_a": {"VERSION": "0001", "NAME": "a", "up": up_a, "down": down_a},
            "0002_b": {"VERSION": "0002", "NAME": "b", "up": up_b, "down": down_b},
        },
    )

    db = _FakeDB()
    await runner.up(db)
    reverted = await runner.down(db, steps=1)
    assert reverted == ["0002_b"]
    assert log[-1] == "down-b"
    assert {d["version"] for d in db[runner.MIGRATIONS_COLLECTION].docs} == {"0001"}


@pytest.mark.asyncio
async def test_status_reports_pending(monkeypatch):
    async def noop(db):
        pass

    _install_fake_versions(
        monkeypatch,
        {
            "0001_a": {"VERSION": "0001", "NAME": "a", "up": noop, "down": noop},
            "0002_b": {"VERSION": "0002", "NAME": "b", "up": noop, "down": noop},
        },
    )
    db = _FakeDB()
    await runner.up(db, target="0001")

    rows = await runner.status(db)
    assert rows == [
        {"version": "0001", "name": "a", "applied": True},
        {"version": "0002", "name": "b", "applied": False},
    ]


@pytest.mark.asyncio
async def test_down_steps_must_be_positive():
    db = _FakeDB()
    with pytest.raises(ValueError):
        await runner.down(db, steps=0)
