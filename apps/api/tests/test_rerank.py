"""Unit tests for the pluggable reranker."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from src.models.search import SearchResult
from src.services.rerank import (
    CohereReranker,
    LocalCrossEncoderReranker,
    _apply_rerank_scores,
    _redact_message,
    build_reranker,
)

pytestmark = pytest.mark.unit


def _mk(chunk_id: str, score: float = 0.5, content: str = "x") -> SearchResult:
    return SearchResult(
        chunk_id=chunk_id,
        document_id=f"d-{chunk_id}",
        content=content,
        similarity=score,
        metadata={},
        document_title=f"Doc {chunk_id}",
        document_source="test",
    )


class _FakeCohereTransport(httpx.AsyncBaseTransport):
    def __init__(self, response_payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = response_payload
        self._status = status_code
        self.calls: list[dict[str, Any]] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        import json

        self.calls.append(
            {
                "url": str(request.url),
                "headers": dict(request.headers),
                "body": json.loads(request.content.decode()) if request.content else {},
            }
        )
        return httpx.Response(
            self._status,
            json=self._payload,
            request=request,
        )


@pytest.mark.asyncio
async def test_cohere_reranker_reorders_by_index_and_updates_scores(monkeypatch):
    """Cohere should reorder results and replace similarity with relevance_score."""
    results = [_mk("a", 0.1), _mk("b", 0.2), _mk("c", 0.3)]
    rerank_payload = {
        "results": [
            {"index": 2, "relevance_score": 0.95},
            {"index": 0, "relevance_score": 0.81},
            {"index": 1, "relevance_score": 0.40},
        ]
    }

    transport = _FakeCohereTransport(rerank_payload)

    async def fake_async_client(*args, **kwargs):
        return httpx.AsyncClient(transport=transport, timeout=kwargs.get("timeout", 5))

    rr = CohereReranker(api_key="sk-test", model="rerank-3.5", timeout_s=2.0)

    # Patch the AsyncClient constructor to inject our fake transport
    real_client = httpx.AsyncClient

    def _ctor(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr("src.services.rerank.httpx.AsyncClient", _ctor)

    out = await rr.rerank("q", results, top_n=3)

    assert [r.chunk_id for r in out] == ["c", "a", "b"]
    assert out[0].similarity == pytest.approx(0.95)
    assert out[1].similarity == pytest.approx(0.81)
    # Headers must include Bearer auth
    assert transport.calls[0]["headers"].get("authorization", "").lower().startswith("bearer ")


@pytest.mark.asyncio
async def test_cohere_reranker_falls_back_on_http_error(monkeypatch):
    """An HTTP failure must not raise — return the original order."""
    results = [_mk("a"), _mk("b")]

    class BoomClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            raise httpx.ConnectError("boom")

    monkeypatch.setattr("src.services.rerank.httpx.AsyncClient", BoomClient)

    rr = CohereReranker(api_key="sk-test")
    out = await rr.rerank("q", results, top_n=2)
    assert [r.chunk_id for r in out] == ["a", "b"]


@pytest.mark.asyncio
async def test_cohere_reranker_handles_partial_response(monkeypatch):
    """If Cohere only returns a subset, backfill from the original order."""
    results = [_mk("a"), _mk("b"), _mk("c")]
    payload = {"results": [{"index": 1, "relevance_score": 0.9}]}

    transport = _FakeCohereTransport(payload)
    real_client = httpx.AsyncClient

    def _ctor(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr("src.services.rerank.httpx.AsyncClient", _ctor)

    rr = CohereReranker(api_key="sk-test")
    out = await rr.rerank("q", results, top_n=3)

    # First should be reranker's pick; rest backfilled in original order.
    assert out[0].chunk_id == "b"
    assert {r.chunk_id for r in out} == {"a", "b", "c"}


def test_apply_rerank_scores_drops_invalid_indices():
    results = [_mk("a"), _mk("b")]
    out = _apply_rerank_scores(
        results,
        [
            {"index": 99, "relevance_score": 0.9},  # OOB
            {"index": -1, "relevance_score": 0.8},  # negative
            {"index": 1, "relevance_score": 0.7},
        ],
        top_n=2,
    )
    assert out[0].chunk_id == "b"
    # Backfill brings in 'a'
    assert {r.chunk_id for r in out} == {"a", "b"}


def test_apply_rerank_scores_dedupes_repeated_indices():
    results = [_mk("a"), _mk("b")]
    out = _apply_rerank_scores(
        results,
        [
            {"index": 0, "relevance_score": 0.9},
            {"index": 0, "relevance_score": 0.5},
        ],
        top_n=2,
    )
    assert [r.chunk_id for r in out] == ["a", "b"]


def test_redact_message_strips_bearer_token():
    msg = "401 Unauthorized: Bearer sk-secret123 invalid"
    redacted = _redact_message(msg)
    assert "sk-secret123" not in redacted
    assert "Bearer <redacted>" in redacted


def test_build_reranker_off_returns_none():
    assert build_reranker(provider="off", api_key=None, model=None) is None
    assert build_reranker(provider=None, api_key=None, model=None) is None


def test_build_reranker_cohere_requires_api_key():
    assert build_reranker(provider="cohere", api_key=None, model=None) is None
    rr = build_reranker(provider="cohere", api_key="sk-test", model=None)
    assert isinstance(rr, CohereReranker)


def test_build_reranker_unknown_provider_returns_none():
    assert build_reranker(provider="weird", api_key="x", model=None) is None


def test_build_reranker_local_returns_local_instance():
    rr = build_reranker(provider="local", api_key=None, model=None)
    assert isinstance(rr, LocalCrossEncoderReranker)


@pytest.mark.asyncio
async def test_local_reranker_falls_back_when_lib_missing(monkeypatch):
    """If sentence_transformers isn't installed, return original order."""
    rr = LocalCrossEncoderReranker(timeout_s=0.5)

    def _explode():
        raise ImportError("sentence_transformers not installed")

    rr._ensure_model = _explode  # type: ignore[assignment]

    results = [_mk("a"), _mk("b")]
    out = await rr.rerank("q", results, top_n=2)
    assert [r.chunk_id for r in out] == ["a", "b"]


@pytest.mark.asyncio
async def test_cohere_reranker_handles_empty_input(monkeypatch):
    rr = CohereReranker(api_key="sk-test")
    out = await rr.rerank("q", [], top_n=5)
    assert out == []


@pytest.mark.asyncio
async def test_cohere_reranker_truncates_long_content(monkeypatch):
    """Document content over the size limit must be truncated before sending."""
    long_content = "x" * 50000
    results = [_mk("a", content=long_content)]
    payload = {"results": [{"index": 0, "relevance_score": 0.9}]}

    transport = _FakeCohereTransport(payload)
    real_client = httpx.AsyncClient

    def _ctor(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr("src.services.rerank.httpx.AsyncClient", _ctor)

    rr = CohereReranker(api_key="sk-test")
    await rr.rerank("q", results, top_n=1)

    sent_doc = transport.calls[0]["body"]["documents"][0]
    assert len(sent_doc) <= 4000
