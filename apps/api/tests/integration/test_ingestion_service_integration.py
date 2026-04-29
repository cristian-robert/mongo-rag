"""Integration tests for IngestionService against a real MongoDB.

Skipped automatically when ``MONGODB_TEST_URI`` is not set. The fixtures
in ``conftest.py`` create and drop a fresh database per test.
"""

from __future__ import annotations

import pytest

from src.services.ingestion.chunker import DocumentChunk
from src.services.ingestion.service import IngestionService

pytestmark = pytest.mark.integration


async def test_create_pending_then_get_status(mongo_db) -> None:
    """A freshly created pending document is readable via get_document_status."""
    service = IngestionService(
        documents_collection=mongo_db["documents"],
        chunks_collection=mongo_db["chunks"],
    )

    doc_id = await service.create_pending_document(
        tenant_id="tenant-A", title="Spec", source="spec.pdf"
    )

    status = await service.get_document_status(doc_id, "tenant-A")
    assert status is not None
    assert status["status"] == "pending"
    assert status["title"] == "Spec"


async def test_get_status_isolated_by_tenant(mongo_db) -> None:
    """Tenant B cannot read Tenant A's document via get_document_status."""
    service = IngestionService(
        documents_collection=mongo_db["documents"],
        chunks_collection=mongo_db["chunks"],
    )
    doc_id = await service.create_pending_document(
        tenant_id="tenant-A", title="Confidential", source="a.pdf"
    )

    leaked = await service.get_document_status(doc_id, "tenant-B")
    assert leaked is None


async def test_store_chunks_writes_with_tenant_id(mongo_db) -> None:
    """store_chunks persists chunks with the correct tenant_id."""
    service = IngestionService(
        documents_collection=mongo_db["documents"],
        chunks_collection=mongo_db["chunks"],
    )
    doc_id = await service.create_pending_document(
        tenant_id="tenant-A", title="Doc", source="doc.pdf"
    )

    chunks = [
        DocumentChunk(
            content=f"chunk {i}",
            index=i,
            start_char=0,
            end_char=len(f"chunk {i}"),
            metadata={"source": "doc.pdf"},
            token_count=2,
            embedding=[0.1] * 4,
        )
        for i in range(3)
    ]

    written = await service.store_chunks(
        chunks=chunks,
        document_id=doc_id,
        tenant_id="tenant-A",
        source="doc.pdf",
        version=1,
        embedding_model="text-embedding-3-small",
    )

    assert written == 3
    count_a = await mongo_db["chunks"].count_documents({"tenant_id": "tenant-A"})
    count_b = await mongo_db["chunks"].count_documents({"tenant_id": "tenant-B"})
    assert count_a == 3
    assert count_b == 0


async def test_store_chunks_replaces_existing_for_document(mongo_db) -> None:
    """Re-storing chunks deletes prior chunks scoped to the same doc+tenant."""
    service = IngestionService(
        documents_collection=mongo_db["documents"],
        chunks_collection=mongo_db["chunks"],
    )
    doc_id = await service.create_pending_document(
        tenant_id="tenant-A", title="Doc", source="doc.pdf"
    )

    def _make(i: int, content: str) -> DocumentChunk:
        return DocumentChunk(
            content=content,
            index=i,
            start_char=0,
            end_char=len(content),
            metadata={"source": "doc.pdf"},
            token_count=1,
            embedding=[0.0] * 4,
        )

    await service.store_chunks(
        [_make(0, "old-1"), _make(1, "old-2")],
        document_id=doc_id,
        tenant_id="tenant-A",
        source="doc.pdf",
        version=1,
        embedding_model="m",
    )
    await service.store_chunks(
        [_make(0, "new-1")],
        document_id=doc_id,
        tenant_id="tenant-A",
        source="doc.pdf",
        version=2,
        embedding_model="m",
    )

    remaining = [c async for c in mongo_db["chunks"].find({"document_id": doc_id})]
    assert len(remaining) == 1
    assert remaining[0]["content"] == "new-1"


async def test_check_duplicate_scoped_to_tenant(mongo_db) -> None:
    """check_duplicate does not match documents owned by another tenant."""
    service = IngestionService(
        documents_collection=mongo_db["documents"],
        chunks_collection=mongo_db["chunks"],
    )

    # Insert a "ready" document for tenant-A directly to set the status field.
    await mongo_db["documents"].insert_one(
        {
            "_id": "doc-A",
            "tenant_id": "tenant-A",
            "title": "T",
            "source": "shared.pdf",
            "content": "x",
            "content_hash": "hash-1",
            "version": 1,
            "status": "ready",
            "chunk_count": 0,
            "metadata": {},
        }
    )

    found_a = await service.check_duplicate("tenant-A", "shared.pdf", "hash-1")
    found_b = await service.check_duplicate("tenant-B", "shared.pdf", "hash-1")

    assert found_a is not None
    assert found_a["_id"] == "doc-A"
    assert found_b is None
