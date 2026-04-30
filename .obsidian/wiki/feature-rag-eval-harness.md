---
title: "Feature: RAG quality evaluation harness"
type: feature
tags: [feature, rag, evaluation, ci, regression]
sources:
  - "apps/api/src/eval/"
  - "PR #56"
related:
  - "[[feature-rag-pipeline-enhancements]]"
  - "[[hybrid-rrf-search]]"
  - "[[feature-rag-agent]]"
created: 2026-04-30
updated: 2026-04-30
status: compiled
---

## Overview

The harness runs a JSONL "golden" question set through the retrieval pipeline (and optionally the answer generator), reports retrieval and answer-quality metrics, and exits non-zero when configured thresholds are missed. Designed to be CI-run on every PR that touches retrieval code.

## GitHub Issues

| Issue | Title | Status |
|-------|-------|--------|
| (PR #56) | feat(eval): RAG quality evaluation harness | merged |

## Content

### Layout — `apps/api/src/eval/`

| File | Purpose |
|---|---|
| `dataset.py` | `load_dataset(path)` reads JSONL into `list[EvalExample]` |
| `metrics.py` | Pure metric functions |
| `runner.py` | `run_eval(dataset, search_fn, ..., tenant_id, k)` orchestrator |
| `judge.py` | `make_openai_judge()` async LLM-judge factory |
| `report.py` | `EvalReport` Pydantic model + `to_markdown()` for CI comments |
| `run.py` | CLI entry — `python -m src.eval.run` |

### Dataset format (JSONL)

```json
{"id": "q1", "question": "...", "expected_answer": "...",
 "expected_chunk_ids": ["c1"], "expected_doc_ids": ["d1"],
 "tags": ["category"]}
```

Only `question` is required. Missing IDs disable the corresponding retrieval metric for that example.

### Metrics (`metrics.py`)

- `recall_at_k(predicted, gold, k)` — fraction of gold IDs in top-k
- `mean_reciprocal_rank(predicted, gold)` — `1 / rank_of_first_gold_hit`
- `ndcg_at_k(predicted, gold, k)` — binary relevance with log2 discount
- `hit_at_k(predicted, gold, k)` — 1.0 if any gold in top-k
- `substring_match(answer, expected, case_sensitive=False)` — 1.0 if expected text appears verbatim
- LLM judge (optional): scores `faithfulness / correctness / relevance` 0–1 each, with a `reasoning` field

### Runner

```python
report = await run_eval(
    dataset=examples,
    search_fn=search_callable,    # (query, tenant_id, k) -> list[SearchResult]
    tenant_id=tenant_id,
    k=10,
    answer_fn=optional_callable,  # (question, results) -> str
    judge_fn=optional_callable,   # (question, expected, answer, context) -> (score, reasoning)
)
```

`EvalReport` aggregates per-example results plus dataset-level means; `to_markdown()` emits a compact table suitable for posting as a PR comment.

### CLI usage

```bash
uv run python -m src.eval.run \
    --dataset path/to/golden.jsonl \
    --tenant <tenant-id> \
    --k 10 \
    --search-type hybrid|semantic|text \
    --out-json report.json \
    --out-md report.md \
    [--llm-judge] \
    [--min-recall 0.5] [--min-mrr 0.3] [--min-ndcg 0.4]
```

The `--min-*` flags are CI gates: if any aggregate metric falls below the threshold, the process exits with code 1. Wire that exit code into a CI job to block merges.

### Where it fits

- Run locally before pushing changes that touch `services/{search,retrieval,rerank,query_rewrite,citations}.py`
- Run in CI as a job that runs the harness against a fixed golden dataset (separate from unit tests because it needs an Atlas instance + embedding API access)
- A regression in `--min-recall` typically points at chunking or embedding-model changes; in `--min-mrr` at reranker or RRF tuning

## Key Takeaways

- JSONL dataset format with optional fields → flexible per-example coverage.
- Five retrieval metrics + substring match + optional LLM judge = enough surface to catch most retrieval regressions.
- CLI threshold flags exit non-zero — designed for CI gating, not just human inspection.
- Run on retrieval-stack changes (`search`, `retrieval`, `rerank`, `query_rewrite`, `citations`).

## See Also

- [[feature-rag-pipeline-enhancements]] — what the harness regression-tests
- [[hybrid-rrf-search]] — the layer that recall@k / MRR / nDCG@k measure
- [[feature-rag-agent]] — the answer-generation side that `answer_fn` and the LLM judge cover
