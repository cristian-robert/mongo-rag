"""Unit tests for ingestion chunker config and DocumentChunk dataclass.

These tests cover behaviour that does not require the heavy
``transformers`` tokenizer download — i.e. config validation and
``DocumentChunk`` invariants.
"""

import pytest

from src.services.ingestion.chunker import ChunkingConfig, DocumentChunk


@pytest.mark.unit
def test_chunking_config_accepts_valid_overlap():
    """ChunkingConfig accepts overlap strictly less than chunk_size."""
    config = ChunkingConfig(chunk_size=1000, chunk_overlap=200)
    assert config.chunk_size == 1000
    assert config.chunk_overlap == 200


@pytest.mark.unit
def test_chunking_config_rejects_overlap_equal_to_chunk_size():
    """ChunkingConfig rejects overlap == chunk_size (would yield no progress)."""
    with pytest.raises(ValueError, match="Chunk overlap must be less than chunk size"):
        ChunkingConfig(chunk_size=500, chunk_overlap=500)


@pytest.mark.unit
def test_chunking_config_rejects_overlap_larger_than_chunk_size():
    """ChunkingConfig rejects overlap greater than chunk_size."""
    with pytest.raises(ValueError, match="Chunk overlap must be less than chunk size"):
        ChunkingConfig(chunk_size=400, chunk_overlap=900)


@pytest.mark.unit
def test_chunking_config_rejects_zero_min_chunk_size():
    """ChunkingConfig rejects min_chunk_size <= 0 to avoid division-by-zero loops."""
    with pytest.raises(ValueError, match="Minimum chunk size must be positive"):
        ChunkingConfig(chunk_size=1000, chunk_overlap=200, min_chunk_size=0)


@pytest.mark.unit
def test_chunking_config_defaults_match_documented_constants():
    """Config defaults are stable — changing them is a behaviour change."""
    config = ChunkingConfig()
    assert config.chunk_size == 1000
    assert config.chunk_overlap == 200
    assert config.max_chunk_size == 2000
    assert config.min_chunk_size == 100
    assert config.max_tokens == 512


@pytest.mark.unit
def test_document_chunk_estimates_token_count_when_missing():
    """DocumentChunk auto-estimates token_count via ~4 chars/token rule."""
    text = "a" * 400
    chunk = DocumentChunk(
        content=text, index=0, start_char=0, end_char=400, metadata={"source": "x"}
    )
    assert chunk.token_count == 100  # 400 // 4


@pytest.mark.unit
def test_document_chunk_preserves_explicit_token_count():
    """DocumentChunk does not overwrite an explicitly-provided token_count."""
    chunk = DocumentChunk(
        content="hello world",
        index=0,
        start_char=0,
        end_char=11,
        metadata={},
        token_count=7,
    )
    assert chunk.token_count == 7


@pytest.mark.unit
def test_document_chunk_embedding_starts_none():
    """Embedding field is None until the embedder fills it in."""
    chunk = DocumentChunk(
        content="x", index=0, start_char=0, end_char=1, metadata={}, token_count=1
    )
    assert chunk.embedding is None
