"""RAG agent with tenant-aware search."""

import logging

from pydantic_ai import Agent

from src.core.dependencies import AgentDependencies
from src.core.prompts import build_system_prompt
from src.core.providers import get_llm_model
from src.models.search import SearchResult
from src.services.search import hybrid_search, semantic_search, text_search

logger = logging.getLogger(__name__)


def create_rag_agent(product_name: str = "this product") -> Agent:
    """Create a RAG agent with a tenant-customized system prompt.

    Args:
        product_name: Tenant's product name for prompt personalization.

    Returns:
        Configured Pydantic AI Agent.
    """
    system_prompt = build_system_prompt(product_name)
    agent = Agent(get_llm_model(), system_prompt=system_prompt)
    return agent


async def run_search(
    deps: AgentDependencies,
    query: str,
    tenant_id: str,
    search_type: str = "hybrid",
    match_count: int = 5,
) -> list[SearchResult]:
    """Run tenant-filtered search using the specified search type.

    Args:
        deps: Initialized AgentDependencies with DB connections.
        query: User's search query.
        tenant_id: Tenant ID for isolation.
        search_type: One of "semantic", "text", "hybrid".
        match_count: Number of results to return.

    Returns:
        List of SearchResult objects.
    """
    if search_type == "semantic":
        return await semantic_search(deps, query, tenant_id, match_count)
    elif search_type == "text":
        return await text_search(deps, query, tenant_id, match_count)
    else:
        return await hybrid_search(deps, query, tenant_id, match_count)


def format_search_context(results: list[SearchResult]) -> str:
    """Format search results into context string for the LLM prompt.

    Args:
        results: List of SearchResult objects.

    Returns:
        Formatted string with numbered source snippets.
    """
    if not results:
        return "No relevant documents found in the knowledge base."

    parts = []
    for i, result in enumerate(results, 1):
        heading = ""
        if result.metadata.get("heading_path"):
            heading = " > ".join(result.metadata["heading_path"]) + "\n"
        parts.append(f"[Source {i}: {result.document_title}]\n{heading}{result.content}")
    return "\n\n---\n\n".join(parts)
