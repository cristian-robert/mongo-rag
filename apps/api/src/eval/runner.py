"""Runner: drives a search function over a dataset and aggregates metrics.

Design:
    - Decoupled from MongoDB. Tests inject a `search_fn` callable;
      the CLI wires in real hybrid_search via a thin adapter.
    - Tenant isolation: tenant_id is passed to every search call. The runner
      itself never reads the gold examples' tenant - the caller controls it.
    - Optional answer judging: enabled only when an explicit `judge_fn` is
      supplied (CLI gates this behind LLM_API_KEY + an opt-in flag).
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable, Optional, Protocol

from src.eval.dataset import EvalExample
from src.eval.metrics import mean_reciprocal_rank, ndcg_at_k, recall_at_k, substring_match
from src.eval.report import EvalReport, EvalRowResult
from src.models.search import SearchResult

logger = logging.getLogger(__name__)

SearchFn = Callable[[str, str, int], Awaitable[list[SearchResult]]]
"""Callable signature: (query, tenant_id, k) -> list[SearchResult]."""

AnswerFn = Callable[[str, list[SearchResult]], Awaitable[str]]
"""Callable signature: (question, top_results) -> generated answer."""


class JudgeFn(Protocol):
    async def __call__(
        self, question: str, expected: str, answer: str, context: str
    ) -> tuple[float, str]:
        """Return (score in [0,1], short reasoning)."""


async def run_eval(
    dataset: list[EvalExample],
    search_fn: SearchFn,
    *,
    tenant_id: str,
    k: int = 10,
    search_type: str = "hybrid",
    dataset_path: str = "<in-memory>",
    answer_fn: Optional[AnswerFn] = None,
    judge_fn: Optional[JudgeFn] = None,
) -> EvalReport:
    """Run the harness and return an aggregated report."""
    if k <= 0:
        raise ValueError("k must be > 0")
    if not tenant_id:
        raise ValueError("tenant_id is required (tenant isolation)")

    rows: list[EvalRowResult] = []
    for example in dataset:
        rows.append(
            await _run_single(
                example,
                search_fn=search_fn,
                tenant_id=tenant_id,
                k=k,
                answer_fn=answer_fn,
                judge_fn=judge_fn,
            )
        )

    aggregate = _aggregate(rows)
    return EvalReport(
        dataset_path=dataset_path,
        tenant_id=tenant_id,
        k=k,
        search_type=search_type,
        total_examples=len(rows),
        examples_with_retrieval_labels=sum(1 for ex in dataset if ex.has_retrieval_labels()),
        examples_with_answer_labels=sum(1 for ex in dataset if ex.expected_answer),
        aggregate=aggregate,
        rows=rows,
    )


async def _run_single(
    example: EvalExample,
    *,
    search_fn: SearchFn,
    tenant_id: str,
    k: int,
    answer_fn: Optional[AnswerFn],
    judge_fn: Optional[JudgeFn],
) -> EvalRowResult:
    row = EvalRowResult(id=example.id, question=example.question)
    try:
        results = await search_fn(example.question, tenant_id, k)
    except Exception as e:  # noqa: BLE001
        logger.exception("eval_search_failed: id=%s", example.id)
        row.error = f"search: {type(e).__name__}: {e}"
        return row

    chunk_ids = [r.chunk_id for r in results]
    doc_ids = [r.document_id for r in results]
    row.predicted_chunk_ids = chunk_ids
    row.predicted_doc_ids = doc_ids

    # Choose label set: prefer chunk-level if provided, else doc-level.
    if example.expected_chunk_ids:
        gold = example.expected_chunk_ids
        predicted = chunk_ids
    else:
        gold = example.expected_doc_ids
        predicted = doc_ids

    if gold:
        row.metrics["recall_at_k"] = recall_at_k(predicted, gold, k)
        row.metrics["mrr"] = mean_reciprocal_rank(predicted, gold)
        row.metrics["ndcg_at_k"] = ndcg_at_k(predicted, gold, k)
        row.metrics["hit_at_k"] = 1.0 if row.metrics["recall_at_k"] > 0 else 0.0

    if answer_fn is not None:
        try:
            row.answer = await answer_fn(example.question, results)
        except Exception as e:  # noqa: BLE001
            logger.exception("eval_answer_failed: id=%s", example.id)
            row.error = f"answer: {type(e).__name__}: {e}"
            return row

        if example.expected_answer:
            row.metrics["answer_substring"] = substring_match(row.answer, example.expected_answer)

        if judge_fn is not None and example.expected_answer:
            context = "\n\n".join(r.content for r in results)
            try:
                score, reasoning = await judge_fn(
                    example.question, example.expected_answer, row.answer, context
                )
                row.judge_score = float(score)
                row.judge_reasoning = reasoning
                row.metrics["judge_score"] = float(score)
            except Exception as e:  # noqa: BLE001
                logger.exception("eval_judge_failed: id=%s", example.id)
                row.error = f"judge: {type(e).__name__}: {e}"

    return row


def _aggregate(rows: list[EvalRowResult]) -> dict[str, float]:
    """Average each metric across rows that reported it.

    Skipping rows without a metric (rather than treating absence as 0) avoids
    deflating scores for examples that lacked the necessary labels.
    """
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for row in rows:
        for name, value in row.metrics.items():
            sums[name] = sums.get(name, 0.0) + float(value)
            counts[name] = counts.get(name, 0) + 1
    return {name: sums[name] / counts[name] for name in sums if counts[name]}


# --- Adapter for the production hybrid search ----------------------------------


def make_default_search_fn(deps, search_type: str = "hybrid") -> SearchFn:
    """Bind production search functions to a runner-shaped callable."""
    from src.services.search import hybrid_search, semantic_search, text_search

    if search_type == "semantic":
        backend = semantic_search
    elif search_type == "text":
        backend = text_search
    elif search_type == "hybrid":
        backend = hybrid_search
    else:
        raise ValueError(f"Unknown search_type: {search_type!r}")

    async def _call(query: str, tenant_id: str, k: int) -> list[SearchResult]:
        return await backend(deps, query, tenant_id, k)

    return _call


__all__ = ["AnswerFn", "JudgeFn", "SearchFn", "make_default_search_fn", "run_eval"]
