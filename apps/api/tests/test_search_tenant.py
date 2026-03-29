"""Tests for tenant-filtered search functions."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.search import SearchResult


@pytest.mark.unit
async def test_semantic_search_includes_tenant_filter():
    """semantic_search passes tenant_id to $vectorSearch filter."""
    from src.services.search import semantic_search

    captured_pipelines = []
    mock_collection = MagicMock()

    async def capture_aggregate(pipeline):
        captured_pipelines.append(pipeline)

        class EmptyCursor:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise StopAsyncIteration

        return EmptyCursor()

    mock_collection.aggregate = capture_aggregate

    ctx = MagicMock()
    ctx.deps = MagicMock()
    ctx.deps.settings = MagicMock()
    ctx.deps.settings.default_match_count = 10
    ctx.deps.settings.max_match_count = 50
    ctx.deps.settings.mongodb_vector_index = "vector_index"
    ctx.deps.settings.mongodb_collection_documents = "documents"
    ctx.deps.settings.mongodb_collection_chunks = "chunks"
    ctx.deps.get_embedding = AsyncMock(return_value=[0.1] * 1536)
    ctx.deps.db = MagicMock()
    ctx.deps.db.__getitem__ = MagicMock(return_value=mock_collection)

    results = await semantic_search(ctx, "test query", tenant_id="tenant-abc")

    assert len(captured_pipelines) == 1
    pipeline = captured_pipelines[0]
    vector_stage = pipeline[0]["$vectorSearch"]
    assert vector_stage["filter"] == {"tenant_id": "tenant-abc"}


@pytest.mark.unit
async def test_text_search_includes_tenant_filter():
    """text_search passes tenant_id to $search compound filter."""
    from src.services.search import text_search

    captured_pipelines = []
    mock_collection = MagicMock()

    async def capture_aggregate(pipeline):
        captured_pipelines.append(pipeline)

        class EmptyCursor:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise StopAsyncIteration

        return EmptyCursor()

    mock_collection.aggregate = capture_aggregate

    ctx = MagicMock()
    ctx.deps = MagicMock()
    ctx.deps.settings = MagicMock()
    ctx.deps.settings.default_match_count = 10
    ctx.deps.settings.max_match_count = 50
    ctx.deps.settings.mongodb_text_index = "text_index"
    ctx.deps.settings.mongodb_collection_documents = "documents"
    ctx.deps.settings.mongodb_collection_chunks = "chunks"
    ctx.deps.db = MagicMock()
    ctx.deps.db.__getitem__ = MagicMock(return_value=mock_collection)

    results = await text_search(ctx, "test query", tenant_id="tenant-abc")

    assert len(captured_pipelines) == 1
    pipeline = captured_pipelines[0]
    search_stage = pipeline[0]["$search"]
    assert "compound" in search_stage
    filter_clause = search_stage["compound"]["filter"]
    assert any(
        f.get("equals", {}).get("value") == "tenant-abc"
        for f in filter_clause
    )


@pytest.mark.unit
async def test_search_without_tenant_id_raises():
    """Search functions require tenant_id parameter."""
    from src.services.search import semantic_search

    ctx = MagicMock()
    with pytest.raises(TypeError):
        await semantic_search(ctx, "test query")  # Missing tenant_id
