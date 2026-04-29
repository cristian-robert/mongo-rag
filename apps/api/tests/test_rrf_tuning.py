"""Tests for tunable RRF parameters."""

from __future__ import annotations

import pytest

from src.models.search import SearchResult
from src.services.search import reciprocal_rank_fusion

pytestmark = pytest.mark.unit


def _mk(chunk_id: str) -> SearchResult:
    return SearchResult(
        chunk_id=chunk_id,
        document_id=f"d-{chunk_id}",
        content="x",
        similarity=0.5,
        metadata={},
        document_title=f"Doc {chunk_id}",
        document_source="test",
    )


def test_rrf_score_decreases_with_larger_k():
    """Larger k flattens score differences between rank positions."""
    results = [[_mk("a"), _mk("b")], [_mk("c"), _mk("a")]]
    fused_60 = reciprocal_rank_fusion(results, k=60)
    fused_5 = reciprocal_rank_fusion(results, k=5)

    a_60 = next(r.similarity for r in fused_60 if r.chunk_id == "a")
    a_5 = next(r.similarity for r in fused_5 if r.chunk_id == "a")
    # k=5 produces larger raw scores than k=60 for the same ranks
    assert a_5 > a_60


def test_rrf_default_k_60_matches_literature():
    """Sanity: at k=60, rank-0 contributes 1/60."""
    results = [[_mk("a")]]
    fused = reciprocal_rank_fusion(results, k=60)
    assert fused[0].similarity == pytest.approx(1 / 60)


def test_rrf_preserves_dedup_across_lists():
    """A chunk appearing in two lists has its scores summed exactly once per list."""
    results = [[_mk("a"), _mk("b")], [_mk("a"), _mk("c")]]
    fused = reciprocal_rank_fusion(results, k=60)
    by_id = {r.chunk_id: r.similarity for r in fused}
    # 'a' rank 0 in both lists → 2 * (1/60)
    assert by_id["a"] == pytest.approx(2 / 60)


def test_rrf_empty_input():
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[]]) == []


def test_rrf_orders_by_combined_score_descending():
    # 'a' wins: rank 0 (best) in list 1, present in list 2.
    # 'd' is only in list 2 at rank 1 → lower combined score.
    results = [[_mk("a"), _mk("b")], [_mk("d"), _mk("a")]]
    fused = reciprocal_rank_fusion(results, k=60)
    assert fused[0].chunk_id == "a"
    # All three should appear in the fused list (dedup correctness)
    assert {r.chunk_id for r in fused} == {"a", "b", "d"}
