"""Search tools for MongoDB RAG Agent."""

import asyncio
import logging
from typing import Dict, List, Optional

from pymongo.errors import OperationFailure

from src.core.dependencies import AgentDependencies
from src.models.search import SearchResult

logger = logging.getLogger(__name__)


async def semantic_search(
    deps: AgentDependencies,
    query: str,
    tenant_id: str,
    match_count: Optional[int] = None,
) -> List[SearchResult]:
    """
    Perform pure semantic search using MongoDB vector similarity.

    Args:
        deps: Agent dependencies with DB connections.
        query: Search query text.
        tenant_id: Tenant ID for isolation.
        match_count: Number of results to return (default: 10).

    Returns:
        List of search results ordered by similarity.
    """
    try:
        # Use default if not specified
        if match_count is None:
            match_count = deps.settings.default_match_count

        # Validate match count
        match_count = min(match_count, deps.settings.max_match_count)

        # Generate embedding for query (already returns list[float])
        query_embedding = await deps.get_embedding(query)

        # Build MongoDB aggregation pipeline
        pipeline = [
            {
                "$vectorSearch": {
                    "index": deps.settings.mongodb_vector_index,
                    "queryVector": query_embedding,
                    "path": "embedding",
                    "numCandidates": 100,  # Search space (10x limit is good default)
                    "limit": match_count,
                    "filter": {"tenant_id": tenant_id},
                }
            },
            {
                "$lookup": {
                    "from": deps.settings.mongodb_collection_documents,
                    "localField": "document_id",
                    "foreignField": "_id",
                    "as": "document_info",
                }
            },
            {"$unwind": "$document_info"},
            {
                "$project": {
                    "chunk_id": "$_id",
                    "document_id": 1,
                    "content": 1,
                    "similarity": {"$meta": "vectorSearchScore"},
                    "metadata": 1,
                    "document_title": "$document_info.title",
                    "document_source": "$document_info.source",
                }
            },
        ]

        # Execute aggregation
        collection = deps.db[deps.settings.mongodb_collection_chunks]
        cursor = await collection.aggregate(pipeline)
        results = [doc async for doc in cursor][:match_count]

        # Convert to SearchResult objects (ObjectId → str conversion)
        search_results = [
            SearchResult(
                chunk_id=str(doc["chunk_id"]),
                document_id=str(doc["document_id"]),
                content=doc["content"],
                similarity=doc["similarity"],
                metadata=doc.get("metadata", {}),
                document_title=doc["document_title"],
                document_source=doc["document_source"],
            )
            for doc in results
        ]

        logger.info(
            "semantic_search_completed: query=%s, results=%d, match_count=%d",
            query,
            len(search_results),
            match_count,
        )

        return search_results

    except OperationFailure as e:
        error_code = e.code if hasattr(e, "code") else None
        logger.error(
            "semantic_search_failed: query=%s, error=%s, code=%s",
            query,
            str(e),
            error_code,
        )
        return []
    except Exception as e:
        logger.exception("semantic_search_error: query=%s, error=%s", query, str(e))
        return []


async def text_search(
    deps: AgentDependencies,
    query: str,
    tenant_id: str,
    match_count: Optional[int] = None,
) -> List[SearchResult]:
    """
    Perform full-text search using MongoDB Atlas Search.

    Uses $search operator for keyword matching, fuzzy matching, and phrase matching.
    Works on all Atlas tiers including M0 (free tier).

    Args:
        deps: Agent dependencies with DB connections.
        query: Search query text.
        tenant_id: Tenant ID for isolation.
        match_count: Number of results to return (default: 10).

    Returns:
        List of search results ordered by text relevance.
    """
    try:
        # Use default if not specified
        if match_count is None:
            match_count = deps.settings.default_match_count

        # Validate match count
        match_count = min(match_count, deps.settings.max_match_count)

        # Build MongoDB Atlas Search aggregation pipeline
        pipeline = [
            {
                "$search": {
                    "index": deps.settings.mongodb_text_index,
                    "compound": {
                        "must": [
                            {
                                "text": {
                                    "query": query,
                                    "path": "content",
                                    "fuzzy": {"maxEdits": 2, "prefixLength": 3},
                                }
                            }
                        ],
                        "filter": [{"equals": {"path": "tenant_id", "value": tenant_id}}],
                    },
                }
            },
            {
                "$limit": match_count * 2  # Over-fetch for better RRF results
            },
            {
                "$lookup": {
                    "from": deps.settings.mongodb_collection_documents,
                    "localField": "document_id",
                    "foreignField": "_id",
                    "as": "document_info",
                }
            },
            {"$unwind": "$document_info"},
            {
                "$project": {
                    "chunk_id": "$_id",
                    "document_id": 1,
                    "content": 1,
                    "similarity": {"$meta": "searchScore"},  # Text relevance score
                    "metadata": 1,
                    "document_title": "$document_info.title",
                    "document_source": "$document_info.source",
                }
            },
        ]

        # Execute aggregation
        collection = deps.db[deps.settings.mongodb_collection_chunks]
        cursor = await collection.aggregate(pipeline)
        results = [doc async for doc in cursor][: match_count * 2]

        # Convert to SearchResult objects (ObjectId → str conversion)
        search_results = [
            SearchResult(
                chunk_id=str(doc["chunk_id"]),
                document_id=str(doc["document_id"]),
                content=doc["content"],
                similarity=doc["similarity"],
                metadata=doc.get("metadata", {}),
                document_title=doc["document_title"],
                document_source=doc["document_source"],
            )
            for doc in results
        ]

        logger.info(
            "text_search_completed: query=%s, results=%d, match_count=%d",
            query,
            len(search_results),
            match_count,
        )

        return search_results

    except OperationFailure as e:
        error_code = e.code if hasattr(e, "code") else None
        logger.error("text_search_failed: query=%s, error=%s, code=%s", query, str(e), error_code)
        return []
    except Exception as e:
        logger.exception("text_search_error: query=%s, error=%s", query, str(e))
        return []


def reciprocal_rank_fusion(
    search_results_list: List[List[SearchResult]], k: int = 60
) -> List[SearchResult]:
    """
    Merge multiple ranked lists using Reciprocal Rank Fusion.

    RRF is a simple yet effective algorithm for combining results from different
    search methods. It works by scoring each document based on its rank position
    in each result list.

    Args:
        search_results_list: List of ranked result lists from different searches
        k: RRF constant (default: 60, standard in literature)

    Returns:
        Unified list of results sorted by combined RRF score

    Algorithm:
        For each document d appearing in result lists:
            RRF_score(d) = Σ(1 / (k + rank_i(d)))
        Where rank_i(d) is the position of document d in result list i.

    References:
        - Cormack et al. (2009): "Reciprocal Rank Fusion outperforms the best system"
        - Standard k=60 performs well across various datasets
    """
    # Build score dictionary by chunk_id
    rrf_scores: Dict[str, float] = {}
    chunk_map: Dict[str, SearchResult] = {}

    # Process each search result list
    for results in search_results_list:
        for rank, result in enumerate(results):
            chunk_id = result.chunk_id

            # Calculate RRF contribution: 1 / (k + rank)
            rrf_score = 1.0 / (k + rank)

            # Accumulate score (automatic deduplication)
            if chunk_id in rrf_scores:
                rrf_scores[chunk_id] += rrf_score
            else:
                rrf_scores[chunk_id] = rrf_score
                chunk_map[chunk_id] = result

    # Sort by combined RRF score (descending)
    sorted_chunks = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

    # Build final result list with updated similarity scores
    merged_results = []
    for chunk_id, rrf_score in sorted_chunks:
        result = chunk_map[chunk_id]
        # Create new result with updated similarity (RRF score)
        merged_result = SearchResult(
            chunk_id=result.chunk_id,
            document_id=result.document_id,
            content=result.content,
            similarity=rrf_score,  # Combined RRF score
            metadata=result.metadata,
            document_title=result.document_title,
            document_source=result.document_source,
        )
        merged_results.append(merged_result)

    logger.info(
        "RRF merged %d result lists into %d unique results",
        len(search_results_list),
        len(merged_results),
    )

    return merged_results


async def hybrid_search(
    deps: AgentDependencies,
    query: str,
    tenant_id: str,
    match_count: Optional[int] = None,
    text_weight: Optional[float] = None,
) -> List[SearchResult]:
    """
    Perform hybrid search combining semantic and keyword matching.

    Uses manual Reciprocal Rank Fusion (RRF) to merge vector and text search results.
    Works on all Atlas tiers including M0 (free tier) - no M10+ required!

    Args:
        deps: Agent dependencies with DB connections.
        query: Search query text.
        tenant_id: Tenant ID for isolation.
        match_count: Number of results to return (default: 10).
        text_weight: Weight for text matching (0-1, not used with RRF).

    Returns:
        List of search results sorted by combined RRF score.
    """
    try:
        # Use defaults if not specified
        if match_count is None:
            match_count = deps.settings.default_match_count

        # Validate match count
        match_count = min(match_count, deps.settings.max_match_count)

        # Over-fetch for better RRF results (2x requested count)
        fetch_count = match_count * 2

        logger.info("hybrid_search starting: query='%s', match_count=%d", query, match_count)

        # Run both searches concurrently for performance
        semantic_results, text_results = await asyncio.gather(
            semantic_search(deps, query, tenant_id, fetch_count),
            text_search(deps, query, tenant_id, fetch_count),
            return_exceptions=True,  # Don't fail if one search errors
        )

        # Handle errors gracefully
        if isinstance(semantic_results, Exception):
            logger.warning("Semantic search failed: %s, using text results only", semantic_results)
            semantic_results = []
        if isinstance(text_results, Exception):
            logger.warning("Text search failed: %s, using semantic results only", text_results)
            text_results = []

        # If both failed, return empty
        if not semantic_results and not text_results:
            logger.error("Both semantic and text search failed")
            return []

        # Merge results using Reciprocal Rank Fusion
        merged_results = reciprocal_rank_fusion(
            [semantic_results, text_results],
            k=60,  # Standard RRF constant
        )

        # Return top N results
        final_results = merged_results[:match_count]

        logger.info(
            "hybrid_search_completed: query='%s', semantic=%d, text=%d, merged=%d, returned=%d",
            query,
            len(semantic_results),
            len(text_results),
            len(merged_results),
            len(final_results),
        )

        return final_results

    except Exception as e:
        logger.exception("hybrid_search_error: query=%s, error=%s", query, str(e))
        # Graceful degradation: try semantic-only as last resort
        try:
            logger.info("Falling back to semantic search only")
            return await semantic_search(deps, query, tenant_id, match_count)
        except Exception:
            return []
