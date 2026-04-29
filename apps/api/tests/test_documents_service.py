"""Service-level tests for IngestionService CRUD additions (#18)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from pymongo.errors import OperationFailure

from src.services.ingestion.service import IngestionService


def _now() -> datetime:
    return datetime(2026, 4, 1, tzinfo=timezone.utc)


@pytest.fixture
def service():
    documents = MagicMock()
    chunks = MagicMock()

    # Wire up an async client.start_session() context manager so cascade
    # delete tests can switch between transaction-supported and standalone.
    db = MagicMock()
    client = MagicMock()
    db.client = client
    documents.database = db
    return IngestionService(documents_collection=documents, chunks_collection=chunks)


# --- list_documents ---


@pytest.mark.unit
async def test_list_documents_filters_by_tenant(service):
    """Tenant_id is always added to the filter regardless of caller input."""
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.skip.return_value = cursor
    cursor.limit.return_value = cursor
    cursor.__aiter__ = lambda self: _aiter([])
    service.documents.find = MagicMock(return_value=cursor)
    service.documents.count_documents = AsyncMock(return_value=0)

    items, total = await service.list_documents(tenant_id="t1")
    assert items == []
    assert total == 0

    filter_q = service.documents.find.call_args.args[0]
    assert filter_q == {"tenant_id": "t1"}


@pytest.mark.unit
async def test_list_documents_search_is_regex_safe(service):
    """Special regex characters in search input are escaped."""
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.skip.return_value = cursor
    cursor.limit.return_value = cursor
    cursor.__aiter__ = lambda self: _aiter([])
    service.documents.find = MagicMock(return_value=cursor)
    service.documents.count_documents = AsyncMock(return_value=0)

    await service.list_documents(tenant_id="t1", search=".*evil.*")

    f = service.documents.find.call_args.args[0]
    # Escaped pattern, not raw .*
    assert f["title"]["$regex"].startswith(r"\.")


@pytest.mark.unit
async def test_list_documents_status_filter(service):
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.skip.return_value = cursor
    cursor.limit.return_value = cursor
    cursor.__aiter__ = lambda self: _aiter([])
    service.documents.find = MagicMock(return_value=cursor)
    service.documents.count_documents = AsyncMock(return_value=0)

    await service.list_documents(tenant_id="t1", status="ready")
    assert service.documents.find.call_args.args[0]["status"] == "ready"


@pytest.mark.unit
async def test_list_documents_invalid_sort_field_falls_back(service):
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.skip.return_value = cursor
    cursor.limit.return_value = cursor
    cursor.__aiter__ = lambda self: _aiter([])
    service.documents.find = MagicMock(return_value=cursor)
    service.documents.count_documents = AsyncMock(return_value=0)

    await service.list_documents(tenant_id="t1", sort="; DROP TABLE; --")
    sort_arg = cursor.sort.call_args.args[0]
    # Falls back to created_at; never injects the bogus field
    assert sort_arg[0][0] == "created_at"


# --- update_metadata ---


@pytest.mark.unit
async def test_update_metadata_filters_by_tenant(service):
    service.documents.find_one_and_update = AsyncMock(
        return_value={
            "_id": "d1",
            "tenant_id": "t1",
            "title": "x",
            "source": "s",
            "status": "ready",
            "chunk_count": 0,
            "version": 1,
            "metadata": {},
            "created_at": _now(),
            "updated_at": _now(),
        }
    )
    await service.update_metadata("d1", "t1", title="x")
    f = service.documents.find_one_and_update.call_args.args[0]
    assert f == {"_id": "d1", "tenant_id": "t1"}


@pytest.mark.unit
async def test_update_metadata_no_op_returns_current(service):
    service.documents.find_one = AsyncMock(
        return_value={
            "_id": "d1",
            "tenant_id": "t1",
            "title": "x",
            "source": "s.pdf",
            "status": "ready",
            "chunk_count": 0,
            "version": 1,
            "metadata": {},
            "created_at": _now(),
            "updated_at": _now(),
        }
    )
    res = await service.update_metadata("d1", "t1")  # no fields
    assert res["_id"] == "d1"


# --- delete_document_with_cascade ---


@pytest.mark.unit
async def test_cascade_delete_returns_false_when_missing(service):
    service.documents.find_one = AsyncMock(return_value=None)
    res = await service.delete_document_with_cascade("missing", "t1")
    assert res is False


@pytest.mark.unit
async def test_cascade_delete_uses_transaction_when_supported(service):
    service.documents.find_one = AsyncMock(return_value={"_id": "d1"})

    session = MagicMock()
    session.with_transaction = AsyncMock()

    async def _fake_with_tx(body):
        # Run the body as if we were inside a transaction
        return await body(session)

    session.with_transaction.side_effect = _fake_with_tx

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    service.documents.database.client.start_session = MagicMock(return_value=cm)

    service.chunks.delete_many = AsyncMock(return_value=MagicMock(deleted_count=3))
    delete_result = MagicMock(deleted_count=1)
    service.documents.delete_one = AsyncMock(return_value=delete_result)

    ok = await service.delete_document_with_cascade("d1", "t1")
    assert ok is True
    # chunks delete was scoped by tenant + document
    chunks_filter = service.chunks.delete_many.call_args.args[0]
    assert chunks_filter == {"document_id": "d1", "tenant_id": "t1"}
    # doc delete was scoped by tenant
    doc_filter = service.documents.delete_one.call_args.args[0]
    assert doc_filter == {"_id": "d1", "tenant_id": "t1"}


@pytest.mark.unit
async def test_cascade_delete_falls_back_on_standalone(service):
    """When transactions are unsupported, falls back to sequenced deletes."""
    service.documents.find_one = AsyncMock(return_value={"_id": "d1"})

    cm = MagicMock()
    session = MagicMock()
    err = OperationFailure("Transaction numbers are only allowed on a replica set member or mongos")
    session.with_transaction = AsyncMock(side_effect=err)
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    service.documents.database.client.start_session = MagicMock(return_value=cm)

    service.chunks.delete_many = AsyncMock(return_value=MagicMock(deleted_count=2))
    service.documents.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))

    ok = await service.delete_document_with_cascade("d1", "t1")
    assert ok is True
    # Fallback path: chunks first, then doc — both tenant-scoped
    assert service.chunks.delete_many.call_count == 1
    assert service.documents.delete_one.call_count == 1


@pytest.mark.unit
async def test_bulk_delete_iterates_per_id(service):
    """Bulk delete is per-id so a single id failure can't cascade.

    Returns the total deleted count.
    """
    # First two ids exist, third doesn't.
    service.documents.find_one = AsyncMock(side_effect=[{"_id": "a"}, {"_id": "b"}, None])

    cm = MagicMock()
    session = MagicMock()

    async def _fake_with_tx(body):
        return await body(session)

    session.with_transaction = AsyncMock(side_effect=_fake_with_tx)
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    service.documents.database.client.start_session = MagicMock(return_value=cm)

    service.chunks.delete_many = AsyncMock(return_value=MagicMock(deleted_count=0))
    service.documents.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))

    deleted = await service.bulk_delete_with_cascade(["a", "b", "c"], "t1")
    assert deleted == 2


# --- mark_for_reingestion ---


@pytest.mark.unit
async def test_reingest_skips_when_processing(service):
    """The find filter excludes processing — the call returns None for racing docs."""
    service.documents.find_one_and_update = AsyncMock(return_value=None)
    res = await service.mark_for_reingestion("d1", "t1")
    assert res is None
    f = service.documents.find_one_and_update.call_args.args[0]
    # Tenant scope + status guard both present
    assert f["tenant_id"] == "t1"
    assert f["_id"] == "d1"
    assert f["status"]["$ne"] == "processing"


@pytest.mark.unit
async def test_reingest_flips_to_pending(service):
    service.documents.find_one_and_update = AsyncMock(
        return_value={
            "_id": "d1",
            "tenant_id": "t1",
            "status": "pending",
            "title": "x",
            "source": "s.pdf",
            "chunk_count": 0,
            "version": 1,
            "metadata": {},
            "created_at": _now(),
            "updated_at": _now(),
        }
    )
    res = await service.mark_for_reingestion("d1", "t1")
    assert res["status"] == "pending"
    update = service.documents.find_one_and_update.call_args.args[1]
    assert update["$set"]["status"] == "pending"
    assert update["$set"]["error_message"] is None


# --- helper ---


async def _aiter(items):
    for i in items:
        yield i
