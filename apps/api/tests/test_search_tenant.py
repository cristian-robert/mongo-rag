"""Tests for tenant-filtered search functions."""

from unittest.mock import AsyncMock, MagicMock

import pytest


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

    deps = MagicMock()
    deps.settings = MagicMock()
    deps.settings.default_match_count = 10
    deps.settings.max_match_count = 50
    deps.settings.mongodb_vector_index = "vector_index"
    deps.settings.mongodb_collection_documents = "documents"
    deps.settings.mongodb_collection_chunks = "chunks"
    deps.get_embedding = AsyncMock(return_value=[0.1] * 1536)
    deps.db = MagicMock()
    deps.db.__getitem__ = MagicMock(return_value=mock_collection)

    await semantic_search(deps, "test query", tenant_id="tenant-abc")

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

    deps = MagicMock()
    deps.settings = MagicMock()
    deps.settings.default_match_count = 10
    deps.settings.max_match_count = 50
    deps.settings.mongodb_text_index = "text_index"
    deps.settings.mongodb_collection_documents = "documents"
    deps.settings.mongodb_collection_chunks = "chunks"
    deps.db = MagicMock()
    deps.db.__getitem__ = MagicMock(return_value=mock_collection)

    await text_search(deps, "test query", tenant_id="tenant-abc")

    assert len(captured_pipelines) == 1
    pipeline = captured_pipelines[0]
    search_stage = pipeline[0]["$search"]
    assert "compound" in search_stage
    filter_clause = search_stage["compound"]["filter"]
    assert any(f.get("equals", {}).get("value") == "tenant-abc" for f in filter_clause)


@pytest.mark.unit
async def test_search_without_tenant_id_raises():
    """Search functions require tenant_id parameter."""
    from src.services.search import semantic_search

    deps = MagicMock()
    with pytest.raises(TypeError):
        await semantic_search(deps, "test query")  # Missing tenant_id
