"""Migration runner.

Discovers ``NNNN_<name>.py`` migration modules in ``apps/api/src/migrations/versions``,
applies pending ones in order, records them in ``_migrations``, and supports a
single-step ``down``.

Each version module must define::

    VERSION: str = "0001"  # zero-padded, sortable
    NAME: str = "baseline"

    async def up(db) -> None: ...
    async def down(db) -> None: ...

The runner is idempotent: re-running ``up`` after a successful apply is a no-op.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable, Protocol

from pymongo.asynchronous.database import AsyncDatabase

logger = logging.getLogger(__name__)

MIGRATIONS_COLLECTION = "_migrations"
_VERSION_RE = re.compile(r"^(\d{4,})_([a-z0-9_]+)$")


class MigrationModule(Protocol):
    VERSION: str
    NAME: str

    async def up(self, db: AsyncDatabase) -> None: ...
    async def down(self, db: AsyncDatabase) -> None: ...


@dataclass(frozen=True)
class Migration:
    version: str
    name: str
    up: Callable[[AsyncDatabase], Awaitable[None]]
    down: Callable[[AsyncDatabase], Awaitable[None]]

    @property
    def id(self) -> str:
        return f"{self.version}_{self.name}"


def discover_migrations(package: str = "src.migrations.versions") -> list[Migration]:
    """Import all migration modules in ``package`` and return them sorted by version."""
    try:
        pkg = importlib.import_module(package)
    except ModuleNotFoundError:
        return []

    migrations: list[Migration] = []
    for mod_info in pkgutil.iter_modules(pkg.__path__):
        if mod_info.ispkg or not _VERSION_RE.match(mod_info.name):
            continue
        module = importlib.import_module(f"{package}.{mod_info.name}")
        version = getattr(module, "VERSION", None)
        name = getattr(module, "NAME", None)
        up = getattr(module, "up", None)
        down = getattr(module, "down", None)
        if not (version and name and up and down):
            raise RuntimeError(f"Migration {mod_info.name} missing VERSION/NAME/up/down")
        migrations.append(Migration(version=version, name=name, up=up, down=down))

    migrations.sort(key=lambda m: m.version)
    versions = [m.version for m in migrations]
    if len(set(versions)) != len(versions):
        raise RuntimeError(f"Duplicate migration versions: {versions}")
    return migrations


async def applied_versions(db: AsyncDatabase) -> set[str]:
    cursor = db[MIGRATIONS_COLLECTION].find({}, {"version": 1, "_id": 0})
    return {doc["version"] async for doc in cursor}


async def status(db: AsyncDatabase) -> list[dict]:
    """Return ordered status report for each known migration."""
    migrations = discover_migrations()
    applied = await applied_versions(db)
    return [
        {
            "version": m.version,
            "name": m.name,
            "applied": m.version in applied,
        }
        for m in migrations
    ]


async def up(db: AsyncDatabase, target: str | None = None) -> list[str]:
    """Apply pending migrations up to and including ``target`` (or all)."""
    migrations = discover_migrations()
    applied = await applied_versions(db)
    applied_now: list[str] = []
    for m in migrations:
        if m.version in applied:
            continue
        if target is not None and m.version > target:
            break
        logger.info("migration_apply_start version=%s name=%s", m.version, m.name)
        await m.up(db)
        await db[MIGRATIONS_COLLECTION].insert_one(
            {
                "version": m.version,
                "name": m.name,
                "applied_at": datetime.now(timezone.utc),
            }
        )
        applied_now.append(m.id)
        logger.info("migration_apply_done version=%s", m.version)
    return applied_now


async def down(db: AsyncDatabase, steps: int = 1) -> list[str]:
    """Revert the last ``steps`` applied migrations in reverse order."""
    if steps < 1:
        raise ValueError("steps must be >= 1")
    migrations = {m.version: m for m in discover_migrations()}
    cursor = db[MIGRATIONS_COLLECTION].find({}, {"version": 1, "_id": 0}).sort("version", -1)
    history = [doc async for doc in cursor]
    reverted: list[str] = []
    for doc in history[:steps]:
        version = doc["version"]
        m = migrations.get(version)
        if m is None:
            raise RuntimeError(f"Cannot revert {version}: module not found")
        logger.info("migration_revert_start version=%s", version)
        await m.down(db)
        await db[MIGRATIONS_COLLECTION].delete_one({"version": version})
        reverted.append(m.id)
        logger.info("migration_revert_done version=%s", version)
    return reverted
