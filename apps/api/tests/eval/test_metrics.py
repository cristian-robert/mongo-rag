"""Hand-computed expectations for retrieval and answer metrics."""

from __future__ import annotations

import math

import pytest

from src.eval.metrics import (
    hit_at_k,
    mean_reciprocal_rank,
    ndcg_at_k,
    recall_at_k,
    substring_match,
)

# ---------------- recall_at_k ----------------


@pytest.mark.unit
def test_recall_at_k_full_recovery():
    assert recall_at_k(["a", "b", "c"], ["a", "b"], k=3) == 1.0


@pytest.mark.unit
def test_recall_at_k_partial():
    # 1 of 2 gold items in top-2 -> 0.5
    assert recall_at_k(["a", "x"], ["a", "b"], k=2) == 0.5


@pytest.mark.unit
def test_recall_at_k_respects_cutoff():
    # gold "b" sits at rank 3; with k=2 it is excluded -> recall 0
    assert recall_at_k(["a", "x", "b"], ["b"], k=2) == 0.0


@pytest.mark.unit
def test_recall_at_k_empty_gold_is_zero():
    assert recall_at_k(["a", "b"], [], k=5) == 0.0


@pytest.mark.unit
def test_recall_at_k_zero_k_is_zero():
    assert recall_at_k(["a"], ["a"], k=0) == 0.0


@pytest.mark.unit
def test_recall_at_k_dedupes_gold():
    # Duplicate gold ids should not inflate recall.
    assert recall_at_k(["a"], ["a", "a"], k=3) == 1.0


# ---------------- mean_reciprocal_rank ----------------


@pytest.mark.unit
def test_mrr_first_position():
    assert mean_reciprocal_rank(["a", "b"], ["a"]) == 1.0


@pytest.mark.unit
def test_mrr_third_position():
    # Rank 3 -> 1/3 (1-indexed)
    assert mean_reciprocal_rank(["x", "y", "a"], ["a"]) == pytest.approx(1.0 / 3.0)


@pytest.mark.unit
def test_mrr_no_hit_is_zero():
    assert mean_reciprocal_rank(["x", "y"], ["a"]) == 0.0


@pytest.mark.unit
def test_mrr_uses_first_gold_hit_only():
    # Two gold; first appears at rank 2 -> 1/2.
    assert mean_reciprocal_rank(["x", "b", "a"], ["a", "b"]) == pytest.approx(0.5)


# ---------------- ndcg_at_k ----------------


@pytest.mark.unit
def test_ndcg_perfect_single_hit():
    # Single gold at rank 1: DCG = 1/log2(2) = 1; IDCG = 1; nDCG = 1.
    assert ndcg_at_k(["a", "b"], ["a"], k=2) == pytest.approx(1.0)


@pytest.mark.unit
def test_ndcg_hit_at_rank_2():
    # Single gold at rank 2: DCG = 1/log2(3); IDCG = 1.
    expected = 1.0 / math.log2(3)
    assert ndcg_at_k(["x", "a"], ["a"], k=2) == pytest.approx(expected)


@pytest.mark.unit
def test_ndcg_two_gold_one_hit():
    # Gold = {a,b}; predicted only contains a at rank 1.
    # IDCG with 2 ideal hits = 1/log2(2) + 1/log2(3).
    # DCG = 1/log2(2) = 1.
    idcg = 1.0 + 1.0 / math.log2(3)
    assert ndcg_at_k(["a", "x"], ["a", "b"], k=2) == pytest.approx(1.0 / idcg)


@pytest.mark.unit
def test_ndcg_idcg_capped_by_k():
    # Three gold but k=1 -> ideal can place at most 1.
    assert ndcg_at_k(["a"], ["a", "b", "c"], k=1) == pytest.approx(1.0)


@pytest.mark.unit
def test_ndcg_zero_when_no_hits():
    assert ndcg_at_k(["x"], ["a"], k=5) == 0.0


@pytest.mark.unit
def test_ndcg_empty_gold_is_zero():
    assert ndcg_at_k(["a"], [], k=5) == 0.0


# ---------------- substring_match ----------------


@pytest.mark.unit
def test_substring_match_case_insensitive_default():
    assert substring_match("The Answer Is 42.", "answer is 42") == 1.0


@pytest.mark.unit
def test_substring_match_case_sensitive():
    assert substring_match("foo BAR", "bar", case_sensitive=True) == 0.0
    assert substring_match("foo BAR", "BAR", case_sensitive=True) == 1.0


@pytest.mark.unit
def test_substring_match_collapses_whitespace():
    assert substring_match("hello\n\n  world", "hello world") == 1.0


@pytest.mark.unit
def test_substring_match_empty_expected_is_zero():
    assert substring_match("anything", "") == 0.0


# ---------------- hit_at_k ----------------


@pytest.mark.unit
def test_hit_at_k_true_when_any_in_topk():
    assert hit_at_k(["x", "a", "y"], ["a"], k=3) == 1.0


@pytest.mark.unit
def test_hit_at_k_respects_cutoff():
    assert hit_at_k(["x", "y", "a"], ["a"], k=2) == 0.0
