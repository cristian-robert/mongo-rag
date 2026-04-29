"""Pluggable reranker for RAG retrieval.

Two backends:
    - Cohere `rerank-3.5` (HTTP) when ``RERANK_API_KEY`` is set and provider == "cohere".
    - Local cross-encoder (sentence-transformers) when provider == "local". Heavy
      dependency — only imported lazily and only when explicitly enabled.

Both backends operate on already-fetched candidates. They never re-query MongoDB,
so tenant isolation is preserved by the upstream search call.

Failures are non-fatal: on any error the original ordering is returned. This
guarantees graceful degradation when a remote reranker is slow/unavailable.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, Protocol

import httpx

from src.models.search import SearchResult

logger = logging.getLogger(__name__)


# Default per-call timeout. Reranking should add ≤500ms total — keep this tight
# so the chat path falls back to RRF order rather than blocking the response.
DEFAULT_RERANK_TIMEOUT_S = 1.5


class Reranker(Protocol):
    """Reranks a list of SearchResults given a query."""

    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_n: Optional[int] = None,
    ) -> list[SearchResult]: ...


class CohereReranker:
    """Cohere Rerank v3.5 backend.

    The Cohere endpoint is invoked over HTTPS using the ``RERANK_API_KEY``
    secret. Inputs (chunk content) are sent as opaque text — the reranker does
    not see metadata, so prompt-injected document content cannot escape into
    other tenants. We only use the returned indices and scores; we never echo
    Cohere's response shape into the LLM context.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "rerank-3.5",
        timeout_s: float = DEFAULT_RERANK_TIMEOUT_S,
        base_url: str = "https://api.cohere.com/v2/rerank",
    ) -> None:
        if not api_key:
            raise ValueError("Cohere reranker requires a non-empty api_key")
        self._api_key = api_key
        self._model = model
        self._timeout_s = timeout_s
        self._base_url = base_url

    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_n: Optional[int] = None,
    ) -> list[SearchResult]:
        if not results:
            return results
        n = top_n if top_n is not None else len(results)
        # Truncate document content sent to the reranker — prevents pathological
        # payloads (e.g. injected megabyte chunks) from blowing latency budget.
        documents = [r.content[:4000] for r in results]

        payload = {
            "model": self._model,
            "query": query[:2000],
            "documents": documents,
            "top_n": min(n, len(results)),
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                resp = await client.post(
                    self._base_url,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, asyncio.TimeoutError, ValueError) as e:
            # Never log the api key or full payload; just status + type.
            logger.warning(
                "rerank_cohere_failed: type=%s msg=%s — falling back to RRF order",
                type(e).__name__,
                _redact_message(str(e)),
            )
            return results[:n]

        return _apply_rerank_scores(results, data.get("results", []), top_n=n)


class LocalCrossEncoderReranker:
    """Sentence-transformers cross-encoder fallback.

    Lazy-loaded; only imported when explicitly enabled. Off by default so the
    base image stays slim. Defaults to ms-marco-MiniLM-L-6-v2 which is small,
    fast, and well-validated for retrieval reranking.
    """

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        timeout_s: float = DEFAULT_RERANK_TIMEOUT_S,
    ) -> None:
        self._model_name = model_name
        self._timeout_s = timeout_s
        self._model = None  # Lazy

    def _ensure_model(self) -> None:
        if self._model is None:
            # Imported lazily so the dependency only matters when this backend
            # is enabled. If the import fails, we surface a clear ImportError
            # to the caller (which catches it and falls back to RRF order).
            from sentence_transformers import CrossEncoder  # type: ignore

            self._model = CrossEncoder(self._model_name)

    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_n: Optional[int] = None,
    ) -> list[SearchResult]:
        if not results:
            return results
        n = top_n if top_n is not None else len(results)

        try:
            await asyncio.wait_for(
                asyncio.to_thread(self._ensure_model),
                timeout=self._timeout_s * 4,
            )
            pairs = [(query[:2000], r.content[:4000]) for r in results]
            scores = await asyncio.wait_for(
                asyncio.to_thread(self._model.predict, pairs),  # type: ignore[union-attr]
                timeout=self._timeout_s * 4,
            )
        except (ImportError, asyncio.TimeoutError, Exception) as e:  # noqa: BLE001
            logger.warning(
                "rerank_local_failed: type=%s — falling back to RRF order",
                type(e).__name__,
            )
            return results[:n]

        # Pair scores with original results, sort descending.
        scored = sorted(
            zip(results, [float(s) for s in scores]),
            key=lambda x: x[1],
            reverse=True,
        )
        return [
            SearchResult(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                content=r.content,
                similarity=score,
                metadata=r.metadata,
                document_title=r.document_title,
                document_source=r.document_source,
            )
            for r, score in scored[:n]
        ]


def _apply_rerank_scores(
    original: list[SearchResult],
    rerank_results: list[dict],
    top_n: int,
) -> list[SearchResult]:
    """Reorder ``original`` by Cohere's returned indices + relevance_score."""
    reordered: list[SearchResult] = []
    seen: set[int] = set()
    for item in rerank_results:
        idx = item.get("index")
        if not isinstance(idx, int) or idx < 0 or idx >= len(original):
            continue
        if idx in seen:
            continue
        seen.add(idx)
        score = float(item.get("relevance_score", 0.0))
        src = original[idx]
        reordered.append(
            SearchResult(
                chunk_id=src.chunk_id,
                document_id=src.document_id,
                content=src.content,
                similarity=score,
                metadata=src.metadata,
                document_title=src.document_title,
                document_source=src.document_source,
            )
        )
        if len(reordered) >= top_n:
            break
    # If reranker returned fewer rows than expected (e.g. a partial response),
    # backfill from the original ordering to keep result counts predictable.
    if len(reordered) < min(top_n, len(original)):
        for i, r in enumerate(original):
            if i in seen:
                continue
            reordered.append(r)
            if len(reordered) >= top_n:
                break
    return reordered


def _redact_message(msg: str) -> str:
    """Strip anything that looks like an API key from log messages."""
    if not msg:
        return msg
    redacted = msg
    for marker in ("Bearer ", "api_key=", "Authorization:"):
        if marker in redacted:
            idx = redacted.index(marker)
            redacted = redacted[:idx] + marker + "<redacted>"
    return redacted[:500]


def build_reranker(
    *,
    provider: Optional[str],
    api_key: Optional[str],
    model: Optional[str],
    timeout_s: float = DEFAULT_RERANK_TIMEOUT_S,
) -> Optional[Reranker]:
    """Construct a reranker from settings, or None when disabled.

    - provider="cohere" requires api_key.
    - provider="local" uses the cross-encoder backend (heavy import on first call).
    - any other value (including None / "off") returns None.
    """
    if not provider or provider == "off":
        return None
    if provider == "cohere":
        if not api_key:
            logger.warning("rerank_provider=cohere but RERANK_API_KEY is empty — disabled")
            return None
        return CohereReranker(
            api_key=api_key,
            model=model or "rerank-3.5",
            timeout_s=timeout_s,
        )
    if provider == "local":
        return LocalCrossEncoderReranker(
            model_name=model or "cross-encoder/ms-marco-MiniLM-L-6-v2",
            timeout_s=timeout_s,
        )
    logger.warning("rerank_provider=%s is unknown — disabled", provider)
    return None


__all__ = [
    "CohereReranker",
    "LocalCrossEncoderReranker",
    "Reranker",
    "build_reranker",
    "DEFAULT_RERANK_TIMEOUT_S",
]
