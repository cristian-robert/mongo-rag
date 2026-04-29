"""Lightweight query expansion / rewriting.

Generates 1-3 additional retrieval queries from the user's question. Bounded,
deterministic by default (heuristic), with optional LLM-driven rewriting when
enabled. Off by default.

We never substitute the original query — expansions are *additional* retrieval
inputs whose results are merged via RRF.
"""

from __future__ import annotations

import logging
from typing import Optional

from src.core.dependencies import AgentDependencies

logger = logging.getLogger(__name__)


# Small list of vague trigger phrases. When the query is short and contains
# one of these, a heuristic expansion is appended. Keeps behavior deterministic
# without an LLM round-trip.
_VAGUE_MARKERS = (
    "how do i",
    "how can i",
    "what is",
    "what are",
    "how to",
    "set this up",
    "set it up",
    "do this",
    "this thing",
    "configure this",
)

_REWRITE_SYSTEM_PROMPT = (
    "You rewrite vague user questions into 2 short, specific search queries "
    "for a documentation knowledge base. Output ONLY the queries, one per "
    "line, with no numbering, quotes, or extra commentary. Do not echo the "
    "original question. Do not invent product names. Keep each query under "
    "120 characters."
)


def _looks_vague(query: str) -> bool:
    """Heuristic: short or contains a vague marker."""
    q = query.lower().strip()
    if len(q) <= 25:
        return True
    return any(marker in q for marker in _VAGUE_MARKERS)


def heuristic_expand(query: str, max_expansions: int = 2) -> list[str]:
    """Deterministic, no-LLM query expansion.

    Strips filler words to produce a noun-focused variant, and appends a
    "guide / tutorial" suffix to bias retrieval toward how-tos.
    """
    cleaned = query.strip()
    if not cleaned:
        return []
    expansions: list[str] = []
    lower = cleaned.lower()

    stripped = lower
    for marker in _VAGUE_MARKERS:
        stripped = stripped.replace(marker, "")
    stripped = " ".join(stripped.split())
    if stripped and stripped != lower:
        expansions.append(stripped)

    if "setup" not in lower and "guide" not in lower and "tutorial" not in lower:
        expansions.append(f"{cleaned} guide tutorial steps")

    # Deduplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for q in expansions:
        if q not in seen and q.strip():
            seen.add(q)
            unique.append(q)
    return unique[:max_expansions]


async def llm_expand(
    deps: AgentDependencies,
    query: str,
    max_expansions: int = 2,
    timeout_s: float = 2.0,
) -> list[str]:
    """LLM-backed expansion. Bounded, never recurses, always returns a list.

    Falls back to ``heuristic_expand`` on any error. The LLM only produces
    queries — its output is never echoed back to the user, so prompt injection
    in document content cannot reach this path (it operates on the user's
    question, not retrieved documents).
    """
    try:
        import asyncio

        from pydantic_ai import Agent

        from src.core.providers import get_llm_model

        agent = Agent(get_llm_model(), system_prompt=_REWRITE_SYSTEM_PROMPT)
        result = await asyncio.wait_for(agent.run(query[:1000]), timeout=timeout_s)
        text = str(result.output)
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "query_rewrite_llm_failed: type=%s — falling back to heuristic",
            type(e).__name__,
        )
        return heuristic_expand(query, max_expansions=max_expansions)

    expansions: list[str] = []
    for line in text.splitlines():
        candidate = line.strip().lstrip("-*0123456789.) ").strip()
        if not candidate:
            continue
        if candidate.lower() == query.lower().strip():
            continue
        expansions.append(candidate[:200])
        if len(expansions) >= max_expansions:
            break
    return expansions or heuristic_expand(query, max_expansions=max_expansions)


async def expand_query(
    query: str,
    *,
    enabled: bool,
    deps: Optional[AgentDependencies] = None,
    use_llm: bool = False,
    max_expansions: int = 2,
) -> list[str]:
    """Top-level entry point. Returns extra queries to retrieve with.

    Always returns ``[]`` when disabled or when the query is not vague,
    keeping the default code path unchanged.
    """
    if not enabled:
        return []
    if max_expansions <= 0:
        return []
    if not _looks_vague(query):
        return []
    if use_llm and deps is not None:
        expansions = await llm_expand(deps, query, max_expansions=max_expansions)
    else:
        expansions = heuristic_expand(query, max_expansions=max_expansions)
    if expansions:
        logger.info("query_expanded: original=%r expansions=%d", query[:80], len(expansions))
    return expansions


__all__ = ["expand_query", "heuristic_expand", "llm_expand"]
