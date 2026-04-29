"""Tests for the retrieval orchestrator (rewrite + search + RRF + rerank)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from src.models.search import SearchResult
from src.services.retrieval import RetrievalOptions, retrieve

pytestmark = pytest.mark.unit


def _mk(idx: str, score: float = 0.5) -> SearchResult:
    return SearchResult(
        chunk_id=f"c-{idx}",
        document_id=f"d-{idx}",
        content=f"content-{idx}",
        similarity=score,
        metadata={},
        document_title=f"Doc {idx}",
        document_source="src",
    )


@dataclass
class _FakeSettings:
    """Minimal stand-in for Settings — only fields touched by retrieve()."""

    default_match_count: int = 5
    max_match_count: int = 50
    rrf_k: int = 60
    rerank_provider: str = "off"
    rerank_api_key: Any = None
    rerank_model: Any = None
    rerank_top_n: int = 10
    rerank_timeout_seconds: float = 1.5
    query_rewrite_enabled: bool = False
    query_rewrite_use_llm: bool = False
    query_rewrite_max_expansions: int = 2


@dataclass
class _FakeDeps:
    settings: _FakeSettings = field(default_factory=_FakeSettings)


@pytest.mark.asyncio
async def test_retrieve_requires_tenant_id():
    deps = _FakeDeps()
    with pytest.raises(ValueError):
        await retrieve(deps, "q", "")


@pytest.mark.asyncio
async def test_retrieve_returns_hybrid_results_when_rerank_off():
    deps = _FakeDeps()
    fake_results = [_mk("a"), _mk("b")]
    with patch(
        "src.services.retrieval.hybrid_search",
        new=AsyncMock(return_value=fake_results),
    ):
        outcome = await retrieve(
            deps,
            "what is x?",
            tenant_id="t1",
            options=RetrievalOptions(search_type="hybrid"),
        )
    assert [r.chunk_id for r in outcome.results] == ["c-a", "c-b"]
    assert outcome.rerank_used is False
    assert outcome.rewritten_queries == []


@pytest.mark.asyncio
async def test_retrieve_passes_tenant_id_to_search():
    """Critical security check: tenant_id must reach the search call."""
    deps = _FakeDeps()
    captured: dict[str, Any] = {}

    async def fake_hybrid(d, q, tenant_id, **kwargs):
        captured["tenant_id"] = tenant_id
        captured["query"] = q
        return [_mk("a")]

    with patch("src.services.retrieval.hybrid_search", new=fake_hybrid):
        await retrieve(deps, "q", tenant_id="tenant-XYZ")
    assert captured["tenant_id"] == "tenant-XYZ"


@pytest.mark.asyncio
async def test_retrieve_invokes_reranker_when_enabled():
    deps = _FakeDeps()
    deps.settings.rerank_provider = "cohere"
    deps.settings.rerank_api_key = "sk-test"

    fake_results = [_mk("a"), _mk("b"), _mk("c")]
    reranked = [_mk("c", score=0.99), _mk("a", score=0.7), _mk("b", score=0.4)]

    class _StubReranker:
        async def rerank(self, q, results, top_n=None):
            return reranked

    with (
        patch(
            "src.services.retrieval.hybrid_search",
            new=AsyncMock(return_value=fake_results),
        ),
        patch(
            "src.services.retrieval.build_reranker",
            return_value=_StubReranker(),
        ),
    ):
        outcome = await retrieve(deps, "q", "t1")

    assert outcome.rerank_used is True
    assert [r.chunk_id for r in outcome.results][0] == "c-c"


@pytest.mark.asyncio
async def test_retrieve_falls_back_when_reranker_times_out():
    """If the reranker hangs past the outer timeout, return upstream order."""
    import asyncio

    deps = _FakeDeps()
    deps.settings.rerank_provider = "cohere"
    deps.settings.rerank_api_key = "sk-test"
    deps.settings.rerank_timeout_seconds = 0.05

    fake_results = [_mk("a"), _mk("b")]

    class _SlowReranker:
        async def rerank(self, q, results, top_n=None):
            await asyncio.sleep(5)
            return results

    with (
        patch(
            "src.services.retrieval.hybrid_search",
            new=AsyncMock(return_value=fake_results),
        ),
        patch(
            "src.services.retrieval.build_reranker",
            return_value=_SlowReranker(),
        ),
    ):
        outcome = await retrieve(deps, "q", "t1")

    assert outcome.rerank_used is False
    assert [r.chunk_id for r in outcome.results] == ["c-a", "c-b"]


@pytest.mark.asyncio
async def test_retrieve_respects_explicit_rerank_override_off():
    """An explicit rerank=False in options must override the global setting."""
    deps = _FakeDeps()
    deps.settings.rerank_provider = "cohere"
    deps.settings.rerank_api_key = "sk-test"

    builder_called = False

    def _no_call(**kwargs):
        nonlocal builder_called
        builder_called = True
        return None

    with (
        patch(
            "src.services.retrieval.hybrid_search",
            new=AsyncMock(return_value=[_mk("a")]),
        ),
        patch(
            "src.services.retrieval.build_reranker",
            side_effect=_no_call,
        ),
    ):
        outcome = await retrieve(
            deps,
            "q",
            "t1",
            options=RetrievalOptions(rerank=False),
        )
    assert builder_called is False
    assert outcome.rerank_used is False


@pytest.mark.asyncio
async def test_retrieve_with_query_rewrite_runs_extra_queries():
    deps = _FakeDeps()
    deps.settings.query_rewrite_enabled = True

    calls: list[str] = []

    async def fake_hybrid(d, q, tenant_id, **kwargs):
        calls.append(q)
        # Each query returns a unique chunk so RRF can merge cleanly.
        return [_mk(q[:3])]

    with patch("src.services.retrieval.hybrid_search", new=fake_hybrid):
        outcome = await retrieve(
            deps,
            "how do I set this up?",
            "t1",
            options=RetrievalOptions(query_rewrite=True),
        )

    # Original + at least one expansion
    assert len(calls) >= 2
    assert outcome.rewritten_queries
    # The original query is the first one issued
    assert calls[0] == "how do I set this up?"


@pytest.mark.asyncio
async def test_retrieve_handles_partial_subquery_failure():
    """If one expansion errors, the others still produce results."""
    deps = _FakeDeps()
    deps.settings.query_rewrite_enabled = True

    async def flaky_hybrid(d, q, tenant_id, **kwargs):
        if "guide" in q:
            raise RuntimeError("transient")
        return [_mk("primary")]

    with patch("src.services.retrieval.hybrid_search", new=flaky_hybrid):
        outcome = await retrieve(
            deps,
            "how do I configure this?",
            "t1",
            options=RetrievalOptions(query_rewrite=True),
        )
    assert any(r.chunk_id == "c-primary" for r in outcome.results)


@pytest.mark.asyncio
async def test_retrieve_match_count_clamped_to_max():
    deps = _FakeDeps()
    deps.settings.max_match_count = 3
    big_results = [_mk(f"c{i}") for i in range(10)]
    with patch(
        "src.services.retrieval.hybrid_search",
        new=AsyncMock(return_value=big_results),
    ):
        outcome = await retrieve(
            deps,
            "q",
            "t1",
            options=RetrievalOptions(match_count=50),
        )
    assert len(outcome.results) <= 3
