"""Dataset loader tests (JSONL parsing + validation)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.eval.dataset import EvalExample, load_dataset


@pytest.mark.unit
def test_load_dataset_round_trip(tmp_path: Path):
    path = tmp_path / "ds.jsonl"
    path.write_text(
        "\n".join(
            [
                "# comment line",
                "",
                json.dumps(
                    {
                        "id": "q1",
                        "question": "What is 2+2?",
                        "expected_answer": "4",
                        "expected_chunk_ids": ["c1"],
                    }
                ),
                json.dumps({"question": "Just a question?"}),
            ]
        ),
        encoding="utf-8",
    )

    examples = load_dataset(path)

    assert len(examples) == 2
    assert examples[0].id == "q1"
    assert examples[0].expected_chunk_ids == ["c1"]
    # Auto-assigned id uses line number.
    assert examples[1].id.startswith("ex-")


@pytest.mark.unit
def test_load_dataset_rejects_invalid_json(tmp_path: Path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"question": "ok"}\nnot-json\n', encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSON"):
        load_dataset(path)


@pytest.mark.unit
def test_load_dataset_rejects_duplicate_ids(tmp_path: Path):
    path = tmp_path / "dup.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"id": "x", "question": "q1"}),
                json.dumps({"id": "x", "question": "q2"}),
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Duplicate"):
        load_dataset(path)


@pytest.mark.unit
def test_load_dataset_rejects_empty(tmp_path: Path):
    path = tmp_path / "empty.jsonl"
    path.write_text("# all comments\n\n", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        load_dataset(path)


@pytest.mark.unit
def test_load_dataset_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_dataset(tmp_path / "nope.jsonl")


@pytest.mark.unit
def test_has_retrieval_labels():
    assert EvalExample(id="a", question="q", expected_chunk_ids=["c"]).has_retrieval_labels()
    assert EvalExample(id="b", question="q", expected_doc_ids=["d"]).has_retrieval_labels()
    assert not EvalExample(id="c", question="q").has_retrieval_labels()


@pytest.mark.unit
def test_committed_sample_dataset_loads():
    """The shipped sample dataset must always parse cleanly."""
    path = Path(__file__).parents[2] / "src" / "eval" / "datasets" / "sample.jsonl"
    examples = load_dataset(path)
    assert len(examples) >= 5
    assert all(ex.question for ex in examples)
    assert all(ex.has_retrieval_labels() for ex in examples)
