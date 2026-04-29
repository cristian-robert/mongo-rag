"""Smoke tests for the backup and restore shell scripts.

These tests use ``--dry-run`` so they never invoke ``mongodump`` /
``pg_dump`` / ``aws`` and are safe to run in any environment. They verify:

- the scripts refuse to run with missing required env vars,
- ``--dry-run`` prints the expected plan and exits 0,
- restore scripts refuse to target non-staging URIs without ``--force``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / "scripts" / "backup"

pytestmark = pytest.mark.skipif(not shutil.which("bash"), reason="bash unavailable")


def _run(
    script: str,
    env: dict | None = None,
    args: list[str] | None = None,
) -> subprocess.CompletedProcess:
    full_env = {**os.environ, **(env or {})}
    return subprocess.run(
        ["bash", str(SCRIPTS / script), *(args or [])],
        env=full_env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_mongo_backup_requires_uri():
    env = {k: v for k, v in os.environ.items() if k != "MONGODB_URI"}
    res = subprocess.run(
        ["bash", str(SCRIPTS / "mongo_backup.sh")],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert res.returncode != 0
    assert "MONGODB_URI" in (res.stderr + res.stdout)


def test_mongo_backup_dry_run(tmp_path):
    res = _run(
        "mongo_backup.sh",
        env={"MONGODB_URI": "mongodb://localhost/test", "BACKUP_DIR": str(tmp_path)},
        args=["--dry-run"],
    )
    assert res.returncode == 0, res.stderr
    assert "dry-run" in res.stdout
    # No actual archive should have been written.
    assert not list(tmp_path.glob("*.archive.gz"))


def test_postgres_backup_requires_url():
    env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
    res = subprocess.run(
        ["bash", str(SCRIPTS / "postgres_backup.sh")],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert res.returncode != 0
    assert "DATABASE_URL" in (res.stderr + res.stdout)


def test_postgres_backup_dry_run(tmp_path):
    res = _run(
        "postgres_backup.sh",
        env={"DATABASE_URL": "postgresql://localhost/test", "BACKUP_DIR": str(tmp_path)},
        args=["--dry-run"],
    )
    assert res.returncode == 0, res.stderr
    assert "dry-run" in res.stdout


def test_mongo_restore_refuses_non_staging_without_force(tmp_path):
    archive = tmp_path / "fake.archive.gz"
    archive.write_bytes(b"x")
    res = _run(
        "mongo_restore.sh",
        env={
            "MONGODB_URI": "mongodb://prod-cluster.example/app",
            "ARCHIVE_PATH": str(archive),
        },
    )
    assert res.returncode == 3
    assert "Refusing" in res.stderr or "Refusing" in res.stdout


def test_mongo_restore_allows_staging_dry_run(tmp_path):
    archive = tmp_path / "fake.archive.gz"
    archive.write_bytes(b"x")
    res = _run(
        "mongo_restore.sh",
        env={
            "MONGODB_URI": "mongodb://staging-cluster.example/app",
            "ARCHIVE_PATH": str(archive),
        },
        args=["--dry-run"],
    )
    assert res.returncode == 0, res.stderr
    assert "dry-run" in res.stdout


def test_postgres_restore_refuses_non_staging_without_force(tmp_path):
    archive = tmp_path / "fake.dump"
    archive.write_bytes(b"x")
    res = _run(
        "postgres_restore.sh",
        env={
            "DATABASE_URL": "postgresql://prod-host.example/app",
            "ARCHIVE_PATH": str(archive),
        },
    )
    assert res.returncode == 3
