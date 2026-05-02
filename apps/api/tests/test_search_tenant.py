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


# --- document_filter restriction (#85) -------------------------------------


def _empty_aggregate_capture() -> tuple[MagicMock, list]:
    """Build a mock collection that captures aggregation pipelines."""
    captured: list = []
    coll = MagicMock()

    async def capture_aggregate(pipeline):
        captured.append(pipeline)

        class EmptyCursor:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise StopAsyncIteration

        return EmptyCursor()

    coll.aggregate = capture_aggregate
    return coll, captured


@pytest.mark.unit
async def test_semantic_search_applies_document_id_filter():
    """When document_ids is supplied, $vectorSearch filter narrows by document_id."""
    from bson import ObjectId

    from src.services.search import semantic_search

    coll, captured = _empty_aggregate_capture()

    deps = MagicMock()
    deps.settings = MagicMock()
    deps.settings.default_match_count = 10
    deps.settings.max_match_count = 50
    deps.settings.mongodb_vector_index = "vector_index"
    deps.settings.mongodb_collection_documents = "documents"
    deps.settings.mongodb_collection_chunks = "chunks"
    deps.get_embedding = AsyncMock(return_value=[0.1] * 1536)
    deps.db = MagicMock()
    deps.db.__getitem__ = MagicMock(return_value=coll)

    # Two valid OIDs — must end up as ObjectId in the filter.
    oid_a = ObjectId()
    oid_b = ObjectId()
    await semantic_search(
        deps,
        "test query",
        tenant_id="tenant-abc",
        document_ids=[str(oid_a), str(oid_b)],
    )

    pipeline = captured[0]
    f = pipeline[0]["$vectorSearch"]["filter"]
    assert f["tenant_id"] == "tenant-abc"
    assert f["document_id"] == {"$in": [oid_a, oid_b]}


@pytest.mark.unit
async def test_text_search_applies_document_id_filter():
    """When document_ids is supplied, $search compound.filter restricts by document_id."""
    from bson import ObjectId

    from src.services.search import text_search

    coll, captured = _empty_aggregate_capture()

    deps = MagicMock()
    deps.settings = MagicMock()
    deps.settings.default_match_count = 10
    deps.settings.max_match_count = 50
    deps.settings.mongodb_text_index = "text_index"
    deps.settings.mongodb_collection_documents = "documents"
    deps.settings.mongodb_collection_chunks = "chunks"
    deps.db = MagicMock()
    deps.db.__getitem__ = MagicMock(return_value=coll)

    oid = ObjectId()
    await text_search(
        deps,
        "test query",
        tenant_id="tenant-abc",
        document_ids=[str(oid)],
    )

    pipeline = captured[0]
    filter_clause = pipeline[0]["$search"]["compound"]["filter"]
    # tenant_id equals filter still present
    assert any(f.get("equals", {}).get("value") == "tenant-abc" for f in filter_clause)
    # document_id "in" filter restricts to provided ids
    in_clauses = [f for f in filter_clause if "in" in f]
    assert in_clauses, "expected $search compound filter to include an 'in' clause"
    in_clause = in_clauses[0]["in"]
    assert in_clause["path"] == "document_id"
    assert in_clause["value"] == [oid]


@pytest.mark.unit
async def test_semantic_search_skips_invalid_oids_in_document_filter(caplog):
    """Garbage ids are dropped with a warning, not propagated as strings."""
    from bson import ObjectId

    from src.services.search import semantic_search

    coll, captured = _empty_aggregate_capture()
    deps = MagicMock()
    deps.settings = MagicMock()
    deps.settings.default_match_count = 10
    deps.settings.max_match_count = 50
    deps.settings.mongodb_vector_index = "vector_index"
    deps.settings.mongodb_collection_documents = "documents"
    deps.settings.mongodb_collection_chunks = "chunks"
    deps.get_embedding = AsyncMock(return_value=[0.1] * 1536)
    deps.db = MagicMock()
    deps.db.__getitem__ = MagicMock(return_value=coll)

    oid = ObjectId()
    await semantic_search(
        deps,
        "q",
        tenant_id="tenant-abc",
        document_ids=[str(oid), "not-a-valid-oid"],
    )

    f = captured[0][0]["$vectorSearch"]["filter"]
    assert f["document_id"] == {"$in": [oid]}


@pytest.mark.unit
async def test_semantic_search_no_document_filter_when_list_omitted():
    """document_ids=None → no document_id filter (back-compat path)."""
    from src.services.search import semantic_search

    coll, captured = _empty_aggregate_capture()
    deps = MagicMock()
    deps.settings = MagicMock()
    deps.settings.default_match_count = 10
    deps.settings.max_match_count = 50
    deps.settings.mongodb_vector_index = "vector_index"
    deps.settings.mongodb_collection_documents = "documents"
    deps.settings.mongodb_collection_chunks = "chunks"
    deps.get_embedding = AsyncMock(return_value=[0.1] * 1536)
    deps.db = MagicMock()
    deps.db.__getitem__ = MagicMock(return_value=coll)

    await semantic_search(deps, "q", tenant_id="tenant-abc")

    f = captured[0][0]["$vectorSearch"]["filter"]
    assert f == {"tenant_id": "tenant-abc"}
