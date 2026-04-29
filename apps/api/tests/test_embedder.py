"""Unit tests for the embedder service.

Patches the module-level ``embedding_client`` so we can assert behaviour
without making real OpenAI API calls.
"""

from datetime import datetime
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.ingestion.chunker import DocumentChunk
from src.services.ingestion.embedder import EmbeddingGenerator, create_embedder


def _make_response(vectors: List[List[float]]) -> MagicMock:
    """Build a stub OpenAI embeddings response."""
    response = MagicMock()
    response.data = [MagicMock(embedding=v) for v in vectors]
    return response


@pytest.mark.unit
async def test_generate_embedding_returns_provider_vector():
    """generate_embedding returns the vector from the provider response."""
    embedder = EmbeddingGenerator(model="text-embedding-3-small")

    fake_client = MagicMock()
    fake_client.embeddings.create = AsyncMock(return_value=_make_response([[0.1, 0.2, 0.3]]))

    with patch("src.services.ingestion.embedder.embedding_client", fake_client):
        result = await embedder.generate_embedding("hello")

    assert result == [0.1, 0.2, 0.3]
    fake_client.embeddings.create.assert_awaited_once()
    kwargs = fake_client.embeddings.create.call_args.kwargs
    assert kwargs["input"] == "hello"
    assert kwargs["model"] == "text-embedding-3-small"


@pytest.mark.unit
async def test_generate_embedding_truncates_overlong_text():
    """Texts longer than max_tokens*4 chars are truncated before embedding."""
    embedder = EmbeddingGenerator(model="text-embedding-3-small")
    max_chars = embedder.config["max_tokens"] * 4
    overlong = "x" * (max_chars + 50)

    fake_client = MagicMock()
    fake_client.embeddings.create = AsyncMock(return_value=_make_response([[0.0] * 1536]))

    with patch("src.services.ingestion.embedder.embedding_client", fake_client):
        await embedder.generate_embedding(overlong)

    sent_text = fake_client.embeddings.create.call_args.kwargs["input"]
    assert len(sent_text) == max_chars


@pytest.mark.unit
async def test_generate_embeddings_batch_returns_one_vector_per_text():
    """generate_embeddings_batch preserves order and one-to-one mapping."""
    embedder = EmbeddingGenerator(model="text-embedding-3-small")

    fake_client = MagicMock()
    fake_client.embeddings.create = AsyncMock(return_value=_make_response([[1.0], [2.0], [3.0]]))

    with patch("src.services.ingestion.embedder.embedding_client", fake_client):
        result = await embedder.generate_embeddings_batch(["a", "b", "c"])

    assert result == [[1.0], [2.0], [3.0]]


@pytest.mark.unit
async def test_embed_chunks_returns_empty_for_empty_input():
    """embed_chunks short-circuits with no provider calls for an empty input."""
    embedder = EmbeddingGenerator(model="text-embedding-3-small")

    fake_client = MagicMock()
    fake_client.embeddings.create = AsyncMock()

    with patch("src.services.ingestion.embedder.embedding_client", fake_client):
        result = await embedder.embed_chunks([])

    assert result == []
    fake_client.embeddings.create.assert_not_awaited()


@pytest.mark.unit
async def test_embed_chunks_batches_and_attaches_embeddings():
    """embed_chunks batches by batch_size and attaches embeddings to each chunk."""
    embedder = EmbeddingGenerator(model="text-embedding-3-small", batch_size=2)
    chunks = [
        DocumentChunk(
            content=f"c{i}",
            index=i,
            start_char=0,
            end_char=2,
            metadata={"src": "t"},
            token_count=1,
        )
        for i in range(3)
    ]

    fake_client = MagicMock()
    # 2 batches: first returns 2 vectors, second returns 1
    fake_client.embeddings.create = AsyncMock(
        side_effect=[
            _make_response([[0.1], [0.2]]),
            _make_response([[0.3]]),
        ]
    )

    progress: list = []

    with patch("src.services.ingestion.embedder.embedding_client", fake_client):
        result = await embedder.embed_chunks(
            chunks, progress_callback=lambda c, t: progress.append((c, t))
        )

    assert len(result) == 3
    assert [c.embedding for c in result] == [[0.1], [0.2], [0.3]]
    # Original metadata preserved + augmented
    for c in result:
        assert c.metadata["src"] == "t"
        assert c.metadata["embedding_model"] == "text-embedding-3-small"
        # Generated-at field is an ISO timestamp
        datetime.fromisoformat(c.metadata["embedding_generated_at"])
    assert fake_client.embeddings.create.await_count == 2
    assert progress == [(1, 2), (2, 2)]


@pytest.mark.unit
def test_embedding_dimension_known_models():
    """Embedding dimensions for known models match OpenAI documentation."""
    assert EmbeddingGenerator("text-embedding-3-small").get_embedding_dimension() == 1536
    assert EmbeddingGenerator("text-embedding-3-large").get_embedding_dimension() == 3072
    assert EmbeddingGenerator("text-embedding-ada-002").get_embedding_dimension() == 1536


@pytest.mark.unit
def test_embedding_dimension_falls_back_for_unknown_model():
    """Unknown models default to 1536 dims (matches text-embedding-3-small)."""
    assert EmbeddingGenerator("some-future-model").get_embedding_dimension() == 1536


@pytest.mark.unit
def test_create_embedder_factory():
    """create_embedder returns an EmbeddingGenerator with the requested config."""
    embedder = create_embedder(model="text-embedding-3-large", batch_size=42)
    assert isinstance(embedder, EmbeddingGenerator)
    assert embedder.model == "text-embedding-3-large"
    assert embedder.batch_size == 42
