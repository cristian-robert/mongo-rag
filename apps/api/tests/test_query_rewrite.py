"""Unit tests for query rewriting / expansion."""

from __future__ import annotations

import pytest

from src.services.query_rewrite import (
    _looks_vague,
    expand_query,
    heuristic_expand,
)

pytestmark = pytest.mark.unit


def test_looks_vague_short_query():
    assert _looks_vague("how do I?")
    assert _looks_vague("what is this?")


def test_looks_vague_specific_long_query():
    # Long query with no vague markers — should be considered specific.
    assert not _looks_vague(
        "Explain RRF fusion of vector and text retrieval results in MongoDB Atlas Search."
    )


def test_heuristic_expand_strips_filler_and_appends_guide():
    expansions = heuristic_expand("How do I configure the agent?", max_expansions=3)
    assert len(expansions) <= 3
    # First strips filler
    assert "configure the agent" in expansions[0].lower()
    # Second is a guide variant
    assert any("guide" in e.lower() for e in expansions)


def test_heuristic_expand_empty_input():
    assert heuristic_expand("") == []
    assert heuristic_expand("   ") == []


def test_heuristic_expand_dedupes():
    expansions = heuristic_expand("setup guide", max_expansions=3)
    assert len(set(expansions)) == len(expansions)


@pytest.mark.asyncio
async def test_expand_query_disabled_returns_empty():
    out = await expand_query("how do I set this up?", enabled=False)
    assert out == []


@pytest.mark.asyncio
async def test_expand_query_specific_query_returns_empty():
    """Specific queries (no vague markers, > 25 chars) should not be expanded."""
    long_specific = "Explain RRF fusion of vector and text retrieval results in MongoDB Atlas."
    out = await expand_query(long_specific, enabled=True)
    assert out == []


@pytest.mark.asyncio
async def test_expand_query_vague_returns_expansions():
    out = await expand_query("how do I configure this?", enabled=True, max_expansions=2)
    assert 1 <= len(out) <= 2


@pytest.mark.asyncio
async def test_expand_query_max_zero_returns_empty():
    out = await expand_query("how do I configure this?", enabled=True, max_expansions=0)
    assert out == []
