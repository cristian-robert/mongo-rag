---
title: "Hybrid RRF Search"
type: concept
tags: [rag, search, mongodb]
sources:
  - "coleam00/MongoDB-RAG-Agent reference repo"
  - "apps/api/src/tools.py"
related:
  - "[[feature-rag-agent]]"
  - "[[feature-document-ingestion]]"
created: 2026-04-29
updated: 2026-04-29
status: active
---

## Summary

MongoRAG uses three-tier hybrid retrieval: a `$vectorSearch` over OpenAI embeddings, an Atlas `$search` text query with fuzzy matching, and a Reciprocal Rank Fusion (RRF) merge. The two searches run concurrently via `asyncio.gather` and the merged ranking is what the agent sees as context.

## Content

### The three tiers

1. **Semantic search** — `$vectorSearch` aggregation on `chunks.embedding` (1536 dims, cosine similarity). Index name: `vector_index`. Uses `numCandidates = limit * 10` and a `tenant_id` filter pushed into the operator.
2. **Text search** — Atlas `$search` over `chunks.content` with fuzzy matching (`maxEdits: 2, prefixLength: 3`).
3. **RRF fusion** — for each result list, `score[doc_id] += 1 / (60 + rank)`. The constant 60 is the standard RRF "k" — large enough that the top results don't dominate.

### Pseudocode

```python
async def hybrid_search(query, tenant_id, limit=5):
    embedding = await get_embedding(query)
    vec, txt = await asyncio.gather(
        vector_search(embedding, tenant_id, limit),
        text_search(query, tenant_id, limit),
    )
    scores = {}
    for rank, doc in enumerate(vec):
        scores[doc["_id"]] = scores.get(doc["_id"], 0) + 1 / (60 + rank)
    for rank, doc in enumerate(txt):
        scores[doc["_id"]] = scores.get(doc["_id"], 0) + 1 / (60 + rank)
    top_ids = sorted(scores, key=scores.get, reverse=True)[:limit]
    return [d for d in vec + txt if d["_id"] in top_ids]
```

### Why both, not just vector

Pure vector search misses exact-match queries (e.g. product SKUs, error codes, proper nouns). Text search alone misses paraphrased queries. RRF gives both signals a vote without per-corpus tuning.

## Key Takeaways

- Always push `tenant_id` into the `$vectorSearch` `filter` — never post-filter
- `numCandidates` controls recall vs latency; `limit * 10` is the default tradeoff point
- Vector and text indexes must both exist on `chunks` — vector via Atlas UI, text via Atlas Search UI

## See Also

- [[feature-rag-agent]] — consumes hybrid_search as a Pydantic AI tool
- [[feature-document-ingestion]] — produces the chunks + embeddings this searches
- [[multi-tenancy-tenant-isolation]] — why every search filters by tenant_id
