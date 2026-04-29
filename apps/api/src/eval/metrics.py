"""Retrieval and answer-quality metrics for the RAG eval harness.

Conventions:
    - All ranked-list inputs are 0-indexed lists; rank 1 == position 0.
    - Metrics return 0.0 when the gold set is empty (caller should skip such
      examples; this module does not silently inflate scores).
    - nDCG uses binary relevance with the standard log2(rank+1) discount.
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence


def recall_at_k(predicted: Sequence[str], gold: Iterable[str], k: int) -> float:
    """Recall@k: fraction of gold items present in the top-k predicted ids.

    Returns 0.0 if `gold` is empty (no labels to evaluate against).
    """
    if k <= 0:
        return 0.0
    gold_set = {g for g in gold if g}
    if not gold_set:
        return 0.0
    top_k = list(predicted)[:k]
    hits = sum(1 for item in top_k if item in gold_set)
    return hits / len(gold_set)


def mean_reciprocal_rank(predicted: Sequence[str], gold: Iterable[str]) -> float:
    """Reciprocal rank of the first gold hit. 0.0 if no gold appears.

    Note: per-example reciprocal rank. Caller averages across the dataset to get MRR.
    Rank is 1-indexed: first position contributes 1/1, second 1/2, etc.
    """
    gold_set = {g for g in gold if g}
    if not gold_set:
        return 0.0
    for idx, item in enumerate(predicted):
        if item in gold_set:
            return 1.0 / (idx + 1)
    return 0.0


def ndcg_at_k(predicted: Sequence[str], gold: Iterable[str], k: int) -> float:
    """Binary-relevance nDCG@k with log2 discount.

    DCG = sum_{i=1..k} rel_i / log2(i + 1)   (ranks are 1-indexed)
    IDCG is the DCG of an ideal ranking with min(|gold|, k) hits at the top.
    Returns 0.0 if gold is empty.
    """
    if k <= 0:
        return 0.0
    gold_set = {g for g in gold if g}
    if not gold_set:
        return 0.0
    top_k = list(predicted)[:k]
    dcg = 0.0
    for idx, item in enumerate(top_k):
        if item in gold_set:
            # idx is 0-based; rank is idx+1; discount uses log2(rank+1) = log2(idx+2)
            dcg += 1.0 / math.log2(idx + 2)

    ideal_hits = min(len(gold_set), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    if idcg == 0.0:
        return 0.0
    return dcg / idcg


def substring_match(answer: str, expected: str, *, case_sensitive: bool = False) -> float:
    """1.0 if `expected` appears in `answer`, else 0.0.

    Empty `expected` returns 0.0 (no signal). Whitespace is collapsed before matching
    so multi-line answers do not falsely miss.
    """
    if not expected:
        return 0.0
    a = " ".join(answer.split())
    e = " ".join(expected.split())
    if not case_sensitive:
        a = a.lower()
        e = e.lower()
    return 1.0 if e in a else 0.0


def hit_at_k(predicted: Sequence[str], gold: Iterable[str], k: int) -> float:
    """1.0 if any gold item appears in top-k, else 0.0."""
    if k <= 0:
        return 0.0
    gold_set = {g for g in gold if g}
    if not gold_set:
        return 0.0
    return 1.0 if any(item in gold_set for item in list(predicted)[:k]) else 0.0
