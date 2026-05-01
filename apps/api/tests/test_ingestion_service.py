"""Tests for tenant-aware ingestion service."""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.unit
async def test_create_pending_document():
    """create_pending_document inserts a document with status pending and tenant_id."""
    from src.services.ingestion.service import IngestionService

    mock_docs = MagicMock()
    mock_docs.insert_one = AsyncMock()

    service = IngestionService(documents_collection=mock_docs, chunks_collection=MagicMock())
    doc_id = await service.create_pending_document(
        tenant_id="tenant-1",
        title="Test Doc",
        source="test.pdf",
    )

    assert isinstance(doc_id, str)
    assert len(doc_id) == 36  # UUID format
    call_args = mock_docs.insert_one.call_args[0][0]
    assert call_args["_id"] == doc_id
    assert call_args["tenant_id"] == "tenant-1"
    assert call_args["status"] == "pending"


@pytest.mark.unit
async def test_update_document_status():
    """update_status updates document status and optional fields."""
    from src.services.ingestion.service import IngestionService

    mock_docs = MagicMock()
    mock_docs.update_one = AsyncMock()

    service = IngestionService(documents_collection=mock_docs, chunks_collection=MagicMock())
    await service.update_status("doc-123", "tenant-1", "processing")

    mock_docs.update_one.assert_called_once()
    filter_arg = mock_docs.update_one.call_args[0][0]
    assert filter_arg == {"_id": "doc-123", "tenant_id": "tenant-1"}


@pytest.mark.unit
async def test_check_duplicate_returns_existing():
    """check_duplicate returns existing doc_id when content_hash matches."""
    from src.services.ingestion.service import IngestionService

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(
        return_value={"_id": "existing-doc", "chunk_count": 10, "version": 1}
    )

    service = IngestionService(documents_collection=mock_docs, chunks_collection=MagicMock())
    result = await service.check_duplicate("tenant-1", "test.pdf", "abc123hash")

    assert result is not None
    assert result["_id"] == "existing-doc"
    assert result["chunk_count"] == 10


@pytest.mark.unit
async def test_check_duplicate_returns_none_when_no_match():
    """check_duplicate returns None when no matching content_hash."""
    from src.services.ingestion.service import IngestionService

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=None)

    service = IngestionService(documents_collection=mock_docs, chunks_collection=MagicMock())
    result = await service.check_duplicate("tenant-1", "test.pdf", "abc123hash")

    assert result is None


@pytest.mark.unit
async def test_store_chunks_with_tenant_id_and_chunk_id():
    """store_chunks writes chunks with tenant_id, chunk_id, and embedding_model."""
    from src.services.ingestion.chunker import DocumentChunk
    from src.services.ingestion.service import IngestionService

    mock_chunks = MagicMock()
    mock_chunks.delete_many = AsyncMock()
    mock_chunks.insert_many = AsyncMock()

    service = IngestionService(documents_collection=MagicMock(), chunks_collection=mock_chunks)

    chunks = [
        DocumentChunk(
            content="test content",
            index=0,
            start_char=0,
            end_char=12,
            metadata={"heading_path": ["Section 1"], "content_type": "text"},
            token_count=3,
            embedding=[0.1] * 1536,
        )
    ]

    await service.store_chunks(
        chunks=chunks,
        document_id="doc-1",
        tenant_id="tenant-1",
        source="test.pdf",
        version=1,
        embedding_model="text-embedding-3-small",
    )

    # Old chunks deleted first
    mock_chunks.delete_many.assert_called_once()
    delete_filter = mock_chunks.delete_many.call_args[0][0]
    assert delete_filter["tenant_id"] == "tenant-1"
    assert delete_filter["document_id"] == "doc-1"

    # New chunks inserted
    mock_chunks.insert_many.assert_called_once()
    inserted = mock_chunks.insert_many.call_args[0][0]
    assert len(inserted) == 1
    assert inserted[0]["tenant_id"] == "tenant-1"
    assert "chunk_id" in inserted[0]
    assert inserted[0]["embedding_model"] == "text-embedding-3-small"


@pytest.mark.unit
def test_read_document_raises_on_missing_file(tmp_path):
    """Bug B regression — missing file MUST raise, not return a placeholder string."""
    from src.services.ingestion.ingest import DocumentIngestionPipeline, IngestionConfig

    pipeline = DocumentIngestionPipeline(
        config=IngestionConfig(),
        tenant_id="test-tenant",
        clean_before_ingest=False,
    )
    missing = str(tmp_path / "does-not-exist.pdf")
    with pytest.raises((FileNotFoundError, OSError)):
        pipeline.read_document(missing)


@pytest.mark.unit
def test_read_document_never_returns_error_placeholder(tmp_path):
    """Bug B regression — content must never start with '[Error:' on any path."""
    from src.services.ingestion.ingest import DocumentIngestionPipeline, IngestionConfig

    pipeline = DocumentIngestionPipeline(
        config=IngestionConfig(),
        tenant_id="test-tenant",
        clean_before_ingest=False,
    )
    # A real markdown file should round-trip fine.
    p = tmp_path / "real.md"
    p.write_text("# Hello\n\nWorld")
    content, _ = pipeline.read_document(str(p))
    assert not content.startswith("[Error:")
