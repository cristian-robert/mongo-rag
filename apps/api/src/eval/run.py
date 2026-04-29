"""CLI entrypoint:  uv run python -m src.eval.run --dataset <path> --tenant <id>

Outputs:
    - JSON report (full row detail) to --out-json (default: stdout)
    - Markdown summary to --out-md (default: skipped)

LLM-as-judge:
    Disabled by default. Pass --llm-judge AND set LLM_API_KEY to enable. The
    judge is *additive* - retrieval metrics still run without it.

Regression gate:
    --min-recall, --min-mrr, --min-ndcg cause non-zero exit if aggregate falls
    below the threshold. Useful in CI smoke tests.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from src.eval.dataset import load_dataset
from src.eval.report import EvalReport
from src.eval.runner import make_default_search_fn, run_eval

logger = logging.getLogger("src.eval.run")


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m src.eval.run",
        description="Run the RAG quality evaluation harness.",
    )
    p.add_argument("--dataset", required=True, help="Path to JSONL dataset file.")
    p.add_argument("--tenant", required=True, help="Tenant id for every search call.")
    p.add_argument("--k", type=int, default=10, help="Top-k cutoff (default: 10).")
    p.add_argument(
        "--search-type",
        choices=("hybrid", "semantic", "text"),
        default="hybrid",
        help="Which search backend to evaluate.",
    )
    p.add_argument("--out-json", default="-", help="JSON output path or '-' for stdout.")
    p.add_argument("--out-md", default=None, help="Optional Markdown summary output path.")
    p.add_argument(
        "--llm-judge",
        action="store_true",
        help="Enable LLM-as-judge (requires LLM_API_KEY).",
    )
    p.add_argument("--min-recall", type=float, default=None)
    p.add_argument("--min-mrr", type=float, default=None)
    p.add_argument("--min-ndcg", type=float, default=None)
    p.add_argument("-v", "--verbose", action="store_true")
    return p


async def _amain(argv: Optional[list[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    dataset = load_dataset(args.dataset)
    logger.info("loaded_dataset: path=%s examples=%d", args.dataset, len(dataset))

    from src.core.dependencies import AgentDependencies

    deps = AgentDependencies()
    await deps.initialize()
    try:
        search_fn = make_default_search_fn(deps, search_type=args.search_type)

        judge_fn = None
        if args.llm_judge:
            if not os.environ.get("LLM_API_KEY"):
                logger.error("llm_judge requested but LLM_API_KEY is unset")
                return 2
            from src.eval.judge import make_openai_judge

            judge_fn = await make_openai_judge()
            if judge_fn is None:
                logger.error("llm_judge_unavailable - aborting")
                return 2

        report = await run_eval(
            dataset,
            search_fn,
            tenant_id=args.tenant,
            k=args.k,
            search_type=args.search_type,
            dataset_path=args.dataset,
            judge_fn=judge_fn,
        )
    finally:
        await deps.cleanup()

    _emit_outputs(report, out_json=args.out_json, out_md=args.out_md)

    return _check_thresholds(
        report,
        min_recall=args.min_recall,
        min_mrr=args.min_mrr,
        min_ndcg=args.min_ndcg,
    )


def _emit_outputs(report: EvalReport, *, out_json: str, out_md: Optional[str]) -> None:
    json_blob = report.model_dump_json(indent=2)
    if out_json == "-":
        sys.stdout.write(json_blob + "\n")
    else:
        Path(out_json).write_text(json_blob + "\n", encoding="utf-8")
    if out_md:
        Path(out_md).write_text(report.to_markdown(), encoding="utf-8")


def _check_thresholds(
    report: EvalReport,
    *,
    min_recall: Optional[float],
    min_mrr: Optional[float],
    min_ndcg: Optional[float],
) -> int:
    failures: list[str] = []
    agg = report.aggregate
    if min_recall is not None and agg.get("recall_at_k", 0.0) < min_recall:
        failures.append(f"recall_at_k={agg.get('recall_at_k', 0.0):.3f} < {min_recall}")
    if min_mrr is not None and agg.get("mrr", 0.0) < min_mrr:
        failures.append(f"mrr={agg.get('mrr', 0.0):.3f} < {min_mrr}")
    if min_ndcg is not None and agg.get("ndcg_at_k", 0.0) < min_ndcg:
        failures.append(f"ndcg_at_k={agg.get('ndcg_at_k', 0.0):.3f} < {min_ndcg}")
    if failures:
        sys.stderr.write("regression: " + "; ".join(failures) + "\n")
        return 1
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    return asyncio.run(_amain(argv))


def parse_args_for_test(argv: list[str]) -> argparse.Namespace:
    """Test seam: parse args without running the pipeline."""
    return _build_arg_parser().parse_args(argv)


to_json = json.dumps


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main", "parse_args_for_test"]
