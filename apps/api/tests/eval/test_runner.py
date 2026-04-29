"""Runner tests with mocked search backend.

Verifies:
    - Tenant id is forwarded to every search call (isolation boundary).
    - Per-row metrics + aggregates are computed correctly.
    - Search exceptions are captured per-row, not propagated.
    - Answer + judge hooks fire only when supplied.
    - Examples with no retrieval labels are skipped for retrieval metrics.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.eval.dataset import EvalExample
from src.eval.runner import run_eval
from src.models.search import SearchResult


def _make_result(chunk_id: str, doc_id: str = "doc-x", content: str = "...") -> SearchResult:
    return SearchResult(
        chunk_id=chunk_id,
        document_id=doc_id,
        content=content,
        similarity=0.5,
        metadata={},
        document_title="t",
        document_source="s",
    )


@pytest.mark.unit
async def test_runner_forwards_tenant_id():
    seen: list[tuple[str, str, int]] = []

    async def search_fn(query: str, tenant_id: str, k: int) -> list[SearchResult]:
        seen.append((query, tenant_id, k))
        return [_make_result("c1")]

    dataset = [
        EvalExample(id="a", question="q1", expected_chunk_ids=["c1"]),
        EvalExample(id="b", question="q2", expected_chunk_ids=["c1"]),
    ]
    report = await run_eval(dataset, search_fn, tenant_id="tenant-zzz", k=5)

    assert len(seen) == 2
    assert all(t == "tenant-zzz" for _, t, _ in seen)
    assert all(k == 5 for _, _, k in seen)
    assert report.tenant_id == "tenant-zzz"


@pytest.mark.unit
async def test_runner_rejects_empty_tenant():
    async def search_fn(*_: Any) -> list[SearchResult]:
        return []

    with pytest.raises(ValueError, match="tenant_id"):
        await run_eval([], search_fn, tenant_id="", k=5)


@pytest.mark.unit
async def test_runner_rejects_zero_k():
    async def search_fn(*_: Any) -> list[SearchResult]:
        return []

    with pytest.raises(ValueError, match="k must be > 0"):
        await run_eval([], search_fn, tenant_id="t", k=0)


@pytest.mark.unit
async def test_runner_computes_perfect_recall():
    async def search_fn(query: str, tenant_id: str, k: int) -> list[SearchResult]:
        return [_make_result("c1"), _make_result("c2"), _make_result("c3")]

    dataset = [EvalExample(id="ok", question="q", expected_chunk_ids=["c1", "c2"])]
    report = await run_eval(dataset, search_fn, tenant_id="t", k=3)

    row = report.rows[0]
    assert row.metrics["recall_at_k"] == pytest.approx(1.0)
    assert row.metrics["mrr"] == pytest.approx(1.0)
    assert row.metrics["hit_at_k"] == 1.0
    assert report.aggregate["recall_at_k"] == pytest.approx(1.0)


@pytest.mark.unit
async def test_runner_falls_back_to_doc_ids_when_no_chunk_labels():
    async def search_fn(query: str, tenant_id: str, k: int) -> list[SearchResult]:
        return [_make_result("c1", doc_id="doc-1"), _make_result("c2", doc_id="doc-2")]

    dataset = [EvalExample(id="d", question="q", expected_doc_ids=["doc-2"])]
    report = await run_eval(dataset, search_fn, tenant_id="t", k=2)

    row = report.rows[0]
    assert row.metrics["recall_at_k"] == pytest.approx(1.0)
    assert row.metrics["mrr"] == pytest.approx(0.5)


@pytest.mark.unit
async def test_runner_skips_metrics_when_no_labels():
    async def search_fn(*_: Any) -> list[SearchResult]:
        return [_make_result("c1")]

    dataset = [EvalExample(id="nolabels", question="q")]
    report = await run_eval(dataset, search_fn, tenant_id="t", k=5)

    row = report.rows[0]
    assert "recall_at_k" not in row.metrics
    assert report.examples_with_retrieval_labels == 0


@pytest.mark.unit
async def test_runner_captures_search_errors_per_row():
    async def search_fn(query: str, tenant_id: str, k: int) -> list[SearchResult]:
        if "boom" in query:
            raise RuntimeError("backend exploded")
        return [_make_result("c1")]

    dataset = [
        EvalExample(id="bad", question="boom", expected_chunk_ids=["c1"]),
        EvalExample(id="good", question="ok", expected_chunk_ids=["c1"]),
    ]
    report = await run_eval(dataset, search_fn, tenant_id="t", k=3)

    rows = {r.id: r for r in report.rows}
    assert "RuntimeError" in (rows["bad"].error or "")
    assert rows["good"].error is None
    assert report.aggregate["recall_at_k"] == pytest.approx(1.0)


@pytest.mark.unit
async def test_runner_invokes_answer_and_judge():
    async def search_fn(*_: Any) -> list[SearchResult]:
        return [_make_result("c1")]

    async def answer_fn(question: str, results: list[SearchResult]) -> str:
        return f"the answer is 42 for {question}"

    judge_calls: list[dict] = []

    async def judge_fn(question: str, expected: str, answer: str, context: str):
        judge_calls.append(
            {"question": question, "expected": expected, "answer": answer, "ctx": context}
        )
        return 0.75, "looks ok"

    dataset = [
        EvalExample(
            id="a",
            question="what is the answer?",
            expected_answer="42",
            expected_chunk_ids=["c1"],
        )
    ]
    report = await run_eval(
        dataset,
        search_fn,
        tenant_id="t",
        k=3,
        answer_fn=answer_fn,
        judge_fn=judge_fn,
    )

    row = report.rows[0]
    assert row.metrics["answer_substring"] == 1.0
    assert row.metrics["judge_score"] == pytest.approx(0.75)
    assert len(judge_calls) == 1
    assert "42" in judge_calls[0]["answer"]


@pytest.mark.unit
async def test_runner_skips_judge_when_no_expected_answer():
    """Judge must not run without a gold answer (saves API spend)."""

    async def search_fn(*_: Any) -> list[SearchResult]:
        return [_make_result("c1")]

    async def answer_fn(*_: Any) -> str:
        return "anything"

    judge_calls: list[Any] = []

    async def judge_fn(*args, **kwargs):
        judge_calls.append((args, kwargs))
        return 1.0, ""

    dataset = [EvalExample(id="x", question="q", expected_chunk_ids=["c1"])]
    await run_eval(
        dataset,
        search_fn,
        tenant_id="t",
        k=3,
        answer_fn=answer_fn,
        judge_fn=judge_fn,
    )

    assert judge_calls == []


@pytest.mark.unit
async def test_runner_captures_judge_error_without_killing_run():
    async def search_fn(*_: Any) -> list[SearchResult]:
        return [_make_result("c1")]

    async def answer_fn(*_: Any) -> str:
        return "yes"

    async def judge_fn(*_: Any, **__: Any):
        raise RuntimeError("judge offline")

    dataset = [EvalExample(id="x", question="q", expected_answer="yes", expected_chunk_ids=["c1"])]
    report = await run_eval(
        dataset, search_fn, tenant_id="t", k=3, answer_fn=answer_fn, judge_fn=judge_fn
    )

    row = report.rows[0]
    assert "judge" in (row.error or "")
    assert row.metrics.get("answer_substring") == 1.0


@pytest.mark.unit
async def test_report_markdown_renders():
    async def search_fn(*_: Any) -> list[SearchResult]:
        return [_make_result("c1")]

    dataset = [EvalExample(id="a", question="q", expected_chunk_ids=["c1"])]
    report = await run_eval(dataset, search_fn, tenant_id="t", k=3)
    md = report.to_markdown()
    assert "Aggregate metrics" in md
    assert "recall_at_k" in md


@pytest.mark.unit
def test_cli_arg_parser_wires_flags():
    from src.eval.run import parse_args_for_test

    args = parse_args_for_test(
        [
            "--dataset",
            "ds.jsonl",
            "--tenant",
            "abc",
            "--k",
            "7",
            "--search-type",
            "semantic",
            "--llm-judge",
            "--min-recall",
            "0.5",
        ]
    )
    assert args.dataset == "ds.jsonl"
    assert args.tenant == "abc"
    assert args.k == 7
    assert args.search_type == "semantic"
    assert args.llm_judge is True
    assert args.min_recall == 0.5
