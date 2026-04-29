"""Eval dataset loader.

Dataset format: JSONL — one JSON object per line.

Required fields:
    question (str)
    expected_answer (str)              # gold answer text (substring used for grading)

Optional fields:
    id (str)                           # stable identifier; defaults to line number
    expected_chunk_ids (list[str])     # gold chunk ids for retrieval metrics
    expected_doc_ids (list[str])       # gold document ids (used if chunk ids absent)
    tags (list[str])                   # categorical tags for slice analysis
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, Field, field_validator


class EvalExample(BaseModel):
    """A single labeled eval example."""

    id: str = Field(..., description="Stable identifier for this example")
    question: str = Field(..., min_length=1)
    expected_answer: str = Field(default="", description="Gold answer text")
    expected_chunk_ids: list[str] = Field(default_factory=list)
    expected_doc_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @field_validator("expected_chunk_ids", "expected_doc_ids", mode="before")
    @classmethod
    def _coerce_to_str_list(cls, v: object) -> list[str]:
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x) for x in v]
        raise TypeError("expected_chunk_ids/expected_doc_ids must be a list")

    def has_retrieval_labels(self) -> bool:
        """True when at least one retrieval-grading label is present."""
        return bool(self.expected_chunk_ids) or bool(self.expected_doc_ids)


def load_dataset(path: str | Path) -> list[EvalExample]:
    """Load and validate a JSONL eval dataset.

    Args:
        path: Path to a .jsonl file. Blank lines and lines starting with `#` are skipped.

    Returns:
        List of EvalExample, in file order.

    Raises:
        FileNotFoundError: if path does not exist.
        ValueError: if any line fails JSON parsing or schema validation.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Eval dataset not found: {p}")

    examples: list[EvalExample] = []
    for line_no, raw in _iter_data_lines(p):
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"{p}:{line_no}: invalid JSON ({e.msg})") from e

        if "id" not in obj or obj["id"] in (None, ""):
            obj["id"] = f"ex-{line_no:04d}"

        try:
            examples.append(EvalExample.model_validate(obj))
        except Exception as e:  # pydantic ValidationError
            raise ValueError(f"{p}:{line_no}: schema error: {e}") from e

    if not examples:
        raise ValueError(f"Eval dataset is empty: {p}")

    ids = [e.id for e in examples]
    if len(set(ids)) != len(ids):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        raise ValueError(f"Duplicate example ids in dataset: {dupes}")

    return examples


def _iter_data_lines(path: Path) -> Iterable[tuple[int, str]]:
    with path.open("r", encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, start=1):
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            yield line_no, stripped
