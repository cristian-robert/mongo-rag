"""High-level retrieval orchestrator: query rewrite → search → RRF → rerank.

Sits between the chat service and the existing ``search.py`` primitives. Keeps
the legacy ``run_search`` path intact for callers that don't need the advanced
features.

Tenant isolation:
    Every retrieval call accepts ``tenant_id`` and forwards it unchanged to the
    underlying search functions. The reranker only reorders the results that
    were already tenant-filtered by MongoDB — it never re-fetches data.

Latency budget:
    Default ``rerank_timeout_seconds`` is 1.5s. On any rerank error or timeout
    the upstream RRF order is returned unchanged, so the chat path never
    blocks indefinitely.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional

from src.core.dependencies import AgentDependencies
from src.models.search import SearchResult
from src.services.query_rewrite import expand_query
from src.services.rerank import build_reranker
from src.services.search import hybrid_search, reciprocal_rank_fusion, semantic_search, text_search

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetrievalOptions:
    """Per-call retrieval knobs. Falls back to settings for unspecified fields."""

    search_type: str = "hybrid"
    match_count: Optional[int] = None
    rrf_k: Optional[int] = None
    rerank: Optional[bool] = None
    rerank_top_n: Optional[int] = None
    query_rewrite: Optional[bool] = None
    # Optional whitelist of document_ids (string ObjectIds). When set,
    # search calls restrict their results to these documents in addition
    # to the mandatory tenant_id filter. Used to honour a bot's
    # ``document_filter`` (#85).
    document_ids: Optional[tuple[str, ...]] = None


@dataclass
class RetrievalOutcome:
    """What ``retrieve`` produced. Returned to chat for transparency / eval."""

    results: list[SearchResult]
    rewritten_queries: list[str]
    rerank_used: bool
    elapsed_ms: float


async def _run_base_search(
    deps: AgentDependencies,
    query: str,
    tenant_id: str,
    search_type: str,
    match_count: int,
    rrf_k: int,
    document_ids: Optional[list[str]] = None,
) -> list[SearchResult]:
    if search_type == "semantic":
        return await semantic_search(deps, query, tenant_id, match_count, document_ids=document_ids)
    if search_type == "text":
        return await text_search(deps, query, tenant_id, match_count, document_ids=document_ids)
    return await hybrid_search(
        deps,
        query,
        tenant_id,
        match_count=match_count,
        rrf_k=rrf_k,
        document_ids=document_ids,
    )


async def retrieve(
    deps: AgentDependencies,
    query: str,
    tenant_id: str,
    options: Optional[RetrievalOptions] = None,
) -> RetrievalOutcome:
    """Run the full retrieval pipeline and return the final ranked chunks."""
    if not tenant_id:
        raise ValueError("tenant_id is required (tenant isolation)")

    opts = options or RetrievalOptions()
    settings = deps.settings
    started = time.perf_counter()

    match_count = opts.match_count or settings.default_match_count
    match_count = min(match_count, settings.max_match_count)
    rrf_k = opts.rrf_k or getattr(settings, "rrf_k", 60)

    rewrite_enabled = (
        opts.query_rewrite
        if opts.query_rewrite is not None
        else getattr(settings, "query_rewrite_enabled", False)
    )
    use_llm_rewrite = getattr(settings, "query_rewrite_use_llm", False)
    max_expansions = getattr(settings, "query_rewrite_max_expansions", 2)

    rewritten = await expand_query(
        query,
        enabled=rewrite_enabled,
        deps=deps,
        use_llm=use_llm_rewrite,
        max_expansions=max_expansions,
    )

    queries = [query] + rewritten

    # When we have multiple queries, fetch each in parallel and RRF the lists.
    # Over-fetch a bit since the reranker may still cull aggressively below.
    fetch_count = max(match_count, getattr(settings, "rerank_top_n", match_count))

    document_ids = list(opts.document_ids) if opts.document_ids else None

    fetched_lists = await asyncio.gather(
        *[
            _run_base_search(
                deps,
                q,
                tenant_id,
                opts.search_type,
                fetch_count,
                rrf_k,
                document_ids=document_ids,
            )
            for q in queries
        ],
        return_exceptions=True,
    )
    safe_lists: list[list[SearchResult]] = []
    for i, lst in enumerate(fetched_lists):
        if isinstance(lst, Exception):
            logger.warning(
                "retrieval_subquery_failed: index=%d type=%s",
                i,
                type(lst).__name__,
            )
            continue
        safe_lists.append(lst)

    if not safe_lists:
        return RetrievalOutcome(
            results=[],
            rewritten_queries=rewritten,
            rerank_used=False,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )

    if len(safe_lists) == 1:
        merged = safe_lists[0]
    else:
        merged = reciprocal_rank_fusion(safe_lists, k=rrf_k)

    rerank_enabled = (
        opts.rerank
        if opts.rerank is not None
        else getattr(settings, "rerank_provider", "off") != "off"
    )
    rerank_used = False
    if rerank_enabled and merged:
        reranker = build_reranker(
            provider=getattr(settings, "rerank_provider", None),
            api_key=getattr(settings, "rerank_api_key", None),
            model=getattr(settings, "rerank_model", None),
            timeout_s=getattr(settings, "rerank_timeout_seconds", 1.5),
        )
        if reranker is not None:
            top_n = opts.rerank_top_n or getattr(settings, "rerank_top_n", match_count)
            try:
                # Hard outer timeout — even if a backend ignores its own timeout,
                # we never let the chat path block beyond ~3x the configured budget.
                merged = await asyncio.wait_for(
                    reranker.rerank(query, merged[:top_n], top_n=top_n),
                    timeout=getattr(settings, "rerank_timeout_seconds", 1.5) * 3,
                )
                rerank_used = True
            except asyncio.TimeoutError:
                logger.warning("rerank_outer_timeout — returning RRF order")

    final_results = merged[:match_count]
    elapsed_ms = (time.perf_counter() - started) * 1000

    logger.info(
        "retrieval_completed: tenant=%s queries=%d returned=%d rerank=%s elapsed_ms=%.1f",
        tenant_id,
        len(queries),
        len(final_results),
        rerank_used,
        elapsed_ms,
    )

    return RetrievalOutcome(
        results=final_results,
        rewritten_queries=rewritten,
        rerank_used=rerank_used,
        elapsed_ms=elapsed_ms,
    )


__all__ = ["RetrievalOptions", "RetrievalOutcome", "retrieve"]
