"""Citation extraction and rendering.

The agent's system prompt instructs the LLM to emit numbered markers like
``[1]``, ``[2]`` in its answer, where each number maps to the same-indexed
search result presented in the prompt context. This module:

    1. Builds a stable, numbered context block to pass to the LLM.
    2. Extracts the citation markers actually referenced in the answer.
    3. Resolves them back to ``Citation`` objects exposed in the API response.

We never echo raw chunk metadata into the LLM prompt as machine-parseable
formats (XML / JSON) — the prompt context is plain text only. This blocks the
class of prompt injections that try to hijack tool calls via crafted markup.
"""

from __future__ import annotations

import logging
import re
from typing import Iterable

from src.models.api import Citation
from src.models.search import SearchResult

logger = logging.getLogger(__name__)

# Match ``[1]`` / ``[12]`` style markers. We deliberately do not match ranges
# like ``[1-3]`` — the prompt forbids them.
CITATION_MARKER_RE = re.compile(r"\[(\d{1,2})\]")

CITATION_SNIPPET_LEN = 200


def build_citation_context(results: list[SearchResult]) -> str:
    """Build the numbered, plain-text context block for the LLM prompt.

    Headings (when present) are included as a single-line breadcrumb so the
    model can disambiguate similar chunks from the same document. Document
    content is rendered as plain text — never as XML/JSON — so user-uploaded
    documents containing tags or fenced code don't get parsed as instructions.
    """
    if not results:
        return "No relevant documents found in the knowledge base."

    parts: list[str] = []
    for i, r in enumerate(results, 1):
        heading = ""
        path = r.metadata.get("heading_path") if r.metadata else None
        if isinstance(path, list) and path:
            heading = " > ".join(str(p) for p in path)

        header = f"[{i}] {r.document_title}"
        if heading:
            header += f" — {heading}"
        # Sanitize content lightly: collapse very long whitespace, strip nulls.
        content = r.content.replace("\x00", "").strip()
        parts.append(f"{header}\n{content}")
    return "\n\n---\n\n".join(parts)


def extract_citation_indices(answer: str) -> list[int]:
    """Extract 1-based indices of citation markers in answer order.

    Duplicates are kept on first encounter only, preserving the order they
    appear in the answer text. Returned indices are not validated against the
    available source count — that's the caller's job.
    """
    if not answer:
        return []
    seen: set[int] = set()
    ordered: list[int] = []
    for match in CITATION_MARKER_RE.finditer(answer):
        try:
            idx = int(match.group(1))
        except ValueError:
            continue
        if idx in seen or idx < 1:
            continue
        seen.add(idx)
        ordered.append(idx)
    return ordered


def resolve_citations(
    answer: str,
    results: list[SearchResult],
) -> list[Citation]:
    """Map ``[n]`` markers in the answer to ``Citation`` objects.

    Indices that fall outside the range of available results are dropped.
    Order matches first-appearance in the answer (so widget UIs render the
    citation list in reading order).
    """
    indices = extract_citation_indices(answer)
    citations: list[Citation] = []
    for idx in indices:
        if idx < 1 or idx > len(results):
            continue
        r = results[idx - 1]
        snippet = (r.content or "").strip()[:CITATION_SNIPPET_LEN]
        heading_path: list[str] = []
        if r.metadata and isinstance(r.metadata.get("heading_path"), list):
            heading_path = [str(p) for p in r.metadata["heading_path"]]
        page_number = None
        if r.metadata:
            page = r.metadata.get("page_number") or r.metadata.get("page")
            if isinstance(page, int):
                page_number = page
        citations.append(
            Citation(
                marker=idx,
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                document_title=r.document_title,
                document_source=r.document_source,
                heading_path=heading_path,
                snippet=snippet,
                relevance_score=float(r.similarity),
                page_number=page_number,
            )
        )
    return citations


def filter_to_cited_results(
    results: list[SearchResult],
    cited_indices: Iterable[int],
) -> list[SearchResult]:
    """Return only the SearchResults that the answer cited."""
    valid = [i for i in cited_indices if 1 <= i <= len(results)]
    return [results[i - 1] for i in valid]


__all__ = [
    "CITATION_MARKER_RE",
    "CITATION_SNIPPET_LEN",
    "build_citation_context",
    "extract_citation_indices",
    "filter_to_cited_results",
    "resolve_citations",
]
