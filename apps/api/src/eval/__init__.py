"""RAG quality evaluation harness.

Measures retrieval and answer quality over a labeled dataset of
{question, expected_answer, expected_doc_ids, expected_chunk_ids}.
"""

from src.eval.dataset import EvalExample, load_dataset
from src.eval.metrics import (
    mean_reciprocal_rank,
    ndcg_at_k,
    recall_at_k,
    substring_match,
)
from src.eval.report import EvalReport, EvalRowResult
from src.eval.runner import run_eval

__all__ = [
    "EvalExample",
    "EvalReport",
    "EvalRowResult",
    "load_dataset",
    "mean_reciprocal_rank",
    "ndcg_at_k",
    "recall_at_k",
    "run_eval",
    "substring_match",
]
