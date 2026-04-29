"""Eval report types and formatting helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class EvalRowResult(BaseModel):
    """Per-example result row."""

    id: str
    question: str
    predicted_chunk_ids: list[str] = Field(default_factory=list)
    predicted_doc_ids: list[str] = Field(default_factory=list)
    answer: str = ""
    metrics: dict[str, float] = Field(default_factory=dict)
    judge_score: Optional[float] = None
    judge_reasoning: Optional[str] = None
    error: Optional[str] = None


class EvalReport(BaseModel):
    """Aggregate report across the whole dataset."""

    dataset_path: str
    tenant_id: str
    k: int
    search_type: str
    timestamp_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    total_examples: int = 0
    examples_with_retrieval_labels: int = 0
    examples_with_answer_labels: int = 0
    aggregate: dict[str, float] = Field(default_factory=dict)
    rows: list[EvalRowResult] = Field(default_factory=list)

    def to_markdown(self) -> str:
        """Render a compact Markdown summary suitable for a CI comment."""
        lines: list[str] = []
        lines.append(f"# RAG Eval Report — {self.timestamp_utc}")
        lines.append("")
        lines.append(f"- Dataset: `{self.dataset_path}`")
        lines.append(f"- Tenant: `{self.tenant_id}`")
        lines.append(f"- Search type: `{self.search_type}`")
        lines.append(f"- k: `{self.k}`")
        lines.append(f"- Examples: {self.total_examples}")
        lines.append(f"  - with retrieval labels: {self.examples_with_retrieval_labels}")
        lines.append(f"  - with answer labels: {self.examples_with_answer_labels}")
        lines.append("")
        lines.append("## Aggregate metrics")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("| --- | --- |")
        for name, value in sorted(self.aggregate.items()):
            lines.append(f"| `{name}` | {value:.4f} |")
        lines.append("")
        if self.rows:
            lines.append("## Per-example")
            lines.append("")
            lines.append("| id | recall@k | mrr | ndcg@k | answer | error |")
            lines.append("| --- | --- | --- | --- | --- | --- |")
            for row in self.rows:
                lines.append(
                    "| {id} | {r:.2f} | {m:.2f} | {n:.2f} | {a:.2f} | {e} |".format(
                        id=row.id,
                        r=row.metrics.get("recall_at_k", 0.0),
                        m=row.metrics.get("mrr", 0.0),
                        n=row.metrics.get("ndcg_at_k", 0.0),
                        a=row.metrics.get("answer_substring", 0.0),
                        e=(row.error or "").replace("|", "\\|")[:40],
                    )
                )
        return "\n".join(lines) + "\n"
