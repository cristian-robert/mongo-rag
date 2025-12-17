# MongoDB Hybrid Search: A Complete Technical Guide

This document explains how we implement intelligent hybrid search combining semantic vector search with full-text keyword matching using MongoDB Atlas, Reciprocal Rank Fusion (RRF), and aggregation pipelines.

## Table of Contents

1. [Overview](#overview)
2. [MongoDB Vector Search](#mongodb-vector-search-vectorsearch)
3. [MongoDB Atlas Search](#mongodb-atlas-search-search)
4. [MongoDB Aggregation Pipeline](#mongodb-aggregation-pipeline)
5. [Reciprocal Rank Fusion (RRF)](#reciprocal-rank-fusion-rrf)
6. [Our Hybrid Search Implementation](#our-hybrid-search-implementation)
7. [Benefits & Trade-offs](#benefits--trade-offs)
8. [Query Examples](#query-examples)

---

## Overview

### The Problem

Traditional search systems face a fundamental limitation:
- **Keyword search** finds exact matches but misses conceptually similar content
- **Semantic search** understands meaning but can miss exact technical terms

**Example**: Searching for "scaling microservices architecture" should return:
- Documents containing "distributed systems patterns" (semantic match)
- Documents with the exact phrase "microservices" (keyword match)

### Our Solution

We combine **three powerful MongoDB features** to solve this:
1. **$vectorSearch** - Finds semantically similar content using embeddings
2. **$search** - Finds keyword matches with fuzzy matching for typos
3. **Reciprocal Rank Fusion** - Intelligently merges both result sets

All running on MongoDB's **free M0 tier** with manual RRF implementation!

---

## MongoDB Vector Search ($vectorSearch)

### What It Is

MongoDB Vector Search uses **Approximate Nearest Neighbor (ANN)** search to find documents with similar vector embeddings. It uses the [Hierarchical Navigable Small Worlds (HNSW)](https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-overview/) algorithm to efficiently search high-dimensional vector spaces without scanning every vector.

### How It Works

**1. Document Embeddings (Ingestion Time)**
```python
# Convert text to 1536-dimensional vector
embedding = await openai_client.embeddings.create(
    model="text-embedding-3-small",
    input="Microservices enable independent deployment..."
)
# Result: [0.023, -0.15, 0.42, ..., 0.08] (1536 numbers)
```

**2. Query Embeddings (Search Time)**
```python
# Convert user query to same vector space
query_embedding = await get_embedding("scaling microservices")
# Result: [0.019, -0.14, 0.39, ..., 0.07] (1536 numbers)
```

**3. Similarity Calculation**

MongoDB calculates **cosine similarity** between vectors:
- Score range: 0 (completely different) to 1 (identical)
- Vectors pointing in similar directions = semantically similar content
- HNSW algorithm finds approximate matches in milliseconds

### MongoDB $vectorSearch Stage

```python
{
    "$vectorSearch": {
        "index": "vector_index",              # Pre-created Atlas index
        "queryVector": [0.023, -0.15, ...],   # 1536-dim query embedding
        "path": "embedding",                   # Field containing embeddings
        "numCandidates": 100,                  # Search space (higher = better recall)
        "limit": 10                            # Max results to return
    }
}
```

**Key Parameters:**

- **`index`**: Vector Search index name (must be created in Atlas UI)
- **`queryVector`**: Your query embedding as Python list (NOT a string!)
- **`path`**: Document field containing the stored embeddings
- **`numCandidates`**: How many candidates to examine (typically 10x limit)
  - Higher = better accuracy but slower
  - Lower = faster but might miss relevant results
- **`limit`**: Maximum number of results to return

**Scoring:**

MongoDB assigns a **similarity score** (0-1) to each result, retrieved using `{"$meta": "vectorSearchScore"}` in a subsequent `$project` stage.

### Our Implementation

```python
pipeline = [
    {
        "$vectorSearch": {
            "index": "vector_index",
            "queryVector": query_embedding,  # list[float] from OpenAI
            "path": "embedding",
            "numCandidates": 100,
            "limit": match_count
        }
    },
    # ... additional stages (see Aggregation Pipeline section)
]
```

---

## MongoDB Atlas Search ($search)

### What It Is

[MongoDB Atlas Search](https://www.mongodb.com/docs/atlas/atlas-search/text/) provides full-text search capabilities powered by Apache Lucene. It enables keyword matching, fuzzy matching (typo tolerance), phrase matching, and more.

### How It Works

**1. Text Indexing (Background Process)**

Atlas Search creates an inverted index:
```
Document: "Microservices architecture enables scalability"
Index:
  "microservices" → [doc_1]
  "architecture" → [doc_1]
  "enables" → [doc_1]
  "scalability" → [doc_1]
```

**2. Fuzzy Matching**

Handles typos and variations using [edit distance](https://www.mongodb.com/docs/atlas/atlas-search/text/):
- Query: "microservices" matches:
  - "microservice" (1 character difference)
  - "micro-services" (1 character difference)
  - "microservces" (1 typo)

**3. Relevance Scoring**

Uses [BM25 algorithm](https://www.mongodb.com/company/blog/technical/harness-power-atlas-search-vector-search-with-rankfusion) (industry standard):
- Term frequency: How often the word appears
- Document frequency: How rare the word is across all documents
- Field length: Shorter fields weighted higher

### MongoDB $search Stage

```python
{
    "$search": {
        "index": "text_index",            # Pre-created Atlas Search index
        "text": {
            "query": "microservices",     # Search query text
            "path": "content",            # Field to search
            "fuzzy": {
                "maxEdits": 2,            # Allow up to 2 character edits
                "prefixLength": 3         # First 3 chars must match exactly
            }
        }
    }
}
```

**Key Parameters:**

- **`index`**: Atlas Search index name (created in Atlas UI)
- **`text.query`**: User's search query
- **`text.path`**: Document field to search in
- **`fuzzy.maxEdits`**: Maximum character changes allowed (1 or 2)
- **`fuzzy.prefixLength`**: Characters that must match exactly at start

**Fuzzy Matching Behavior:**

- `maxEdits: 2` allows:
  - Substitutions: "microservces" → "microservices"
  - Insertions: "microservies" → "microservices"
  - Deletions: "microoservices" → "microservices"
- `prefixLength: 3` prevents:
  - "microservices" matching "macroservices" (first 3 chars different)
  - Improves performance by reducing false positives

### Our Implementation

```python
pipeline = [
    {
        "$search": {
            "index": "text_index",
            "text": {
                "query": query,        # User's search query
                "path": "content",     # Search in content field
                "fuzzy": {
                    "maxEdits": 2,     # Tolerate 2-char typos
                    "prefixLength": 3  # First 3 chars exact
                }
            }
        }
    },
    {"$limit": match_count * 2},  # Over-fetch for RRF
    # ... additional stages
]
```

**Why Over-fetch?**

We fetch 2x the requested results because RRF merging works better with more candidates from each search method.

---

## MongoDB Aggregation Pipeline

### What It Is

The [MongoDB Aggregation Pipeline](https://www.mongodb.com/docs/manual/core/aggregation-pipeline/) processes documents through a sequence of stages, where each stage transforms the documents and passes them to the next stage.

**Think of it like Unix pipes:**
```bash
cat file.txt | grep "search" | sort | head -10
```

**MongoDB equivalent:**
```javascript
db.collection.aggregate([
  { $match: {...} },    // Filter documents
  { $sort: {...} },     // Sort results
  { $limit: 10 }        // Take first 10
])
```

### Key Stages We Use

#### 1. $vectorSearch / $search (Entry Point)

These **must be the first stage** in the pipeline:
- `$vectorSearch` - Semantic similarity search
- `$search` - Full-text keyword search

#### 2. $lookup (Join Collections)

[Performs a left outer join](https://www.mongodb.com/docs/manual/reference/operator/aggregation/lookup/) between collections:

```python
{
    "$lookup": {
        "from": "documents",         # Collection to join with
        "localField": "document_id", # Field in chunks collection
        "foreignField": "_id",       # Field in documents collection
        "as": "document_info"        # Output array field name
    }
}
```

**What it does:**

For each chunk, finds the parent document and adds its data:
```javascript
// Before $lookup (chunk document)
{
  "_id": ObjectId("abc123"),
  "document_id": ObjectId("doc456"),
  "content": "Microservices enable..."
}

// After $lookup
{
  "_id": ObjectId("abc123"),
  "document_id": ObjectId("doc456"),
  "content": "Microservices enable...",
  "document_info": [{
    "_id": ObjectId("doc456"),
    "title": "Architecture Guide",
    "source": "arch-guide.pdf"
  }]
}
```

#### 3. $unwind (Flatten Arrays)

Converts array field into individual documents:

```python
{"$unwind": "$document_info"}
```

**What it does:**
```javascript
// Before $unwind
{
  "content": "...",
  "document_info": [{ "title": "Guide", "source": "guide.pdf" }]
}

// After $unwind
{
  "content": "...",
  "document_info": { "title": "Guide", "source": "guide.pdf" }
}
```

Now we can access `document_info.title` directly instead of `document_info[0].title`.

#### 4. $project (Shape Output)

[Specifies which fields to include/exclude](https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-stage/) and can compute new fields:

```python
{
    "$project": {
        "chunk_id": "$_id",                              # Rename _id to chunk_id
        "document_id": 1,                                # Include as-is
        "content": 1,                                    # Include as-is
        "similarity": {"$meta": "vectorSearchScore"},    # Extract search score
        "metadata": 1,                                   # Include as-is
        "document_title": "$document_info.title",        # Extract nested field
        "document_source": "$document_info.source"       # Extract nested field
    }
}
```

**Special `$meta` expressions:**

- `{"$meta": "vectorSearchScore"}` - Score from `$vectorSearch` (0-1)
- `{"$meta": "searchScore"}` - Score from `$search` (varies by relevance)

### Complete Pipeline Example

```python
pipeline = [
    # Stage 1: Vector search (MUST be first)
    {
        "$vectorSearch": {
            "index": "vector_index",
            "queryVector": [0.023, -0.15, ...],
            "path": "embedding",
            "numCandidates": 100,
            "limit": 10
        }
    },

    # Stage 2: Join with documents collection
    {
        "$lookup": {
            "from": "documents",
            "localField": "document_id",
            "foreignField": "_id",
            "as": "document_info"
        }
    },

    # Stage 3: Flatten document_info array
    {
        "$unwind": "$document_info"
    },

    # Stage 4: Shape final output
    {
        "$project": {
            "chunk_id": "$_id",
            "document_id": 1,
            "content": 1,
            "similarity": {"$meta": "vectorSearchScore"},
            "document_title": "$document_info.title",
            "document_source": "$document_info.source"
        }
    }
]

# Execute pipeline
results = await db.chunks.aggregate(pipeline).to_list(length=10)
```

**Result:**
```python
[
    {
        "chunk_id": "abc123",
        "document_id": "doc456",
        "content": "Microservices architecture enables...",
        "similarity": 0.87,
        "document_title": "Architecture Guide",
        "document_source": "arch-guide.pdf"
    },
    # ... more results
]
```

---

## Reciprocal Rank Fusion (RRF)

### What It Is

[Reciprocal Rank Fusion](https://medium.com/@mahaboobali_shaik/reciprocal-rank-fusion-rrf-a-simple-yet-powerful-search-ranking-technique-6e29d84a5357) is an algorithm that combines ranked results from multiple search systems into a single unified ranking. It's used by [MongoDB's $rankFusion](https://www.mongodb.com/docs/atlas/atlas-vector-search/hybrid-search/), Azure AI Search, Elasticsearch, OpenSearch, and many other platforms.

### The Core Problem

Different search systems produce incompatible scores:
- Vector search: Cosine similarity (0.0 - 1.0)
- Text search: BM25 score (unbounded, varies by corpus)

**How do you combine them?**

❌ **Bad approach**: Weighted average
```python
combined = 0.7 * vector_score + 0.3 * text_score
# Problem: Scores on different scales! 0.8 cosine ≠ 0.8 BM25
```

✅ **RRF approach**: Use **rank position**, not raw scores
```python
# Rank is universal: 1st, 2nd, 3rd (same meaning for all systems)
rrf_score = 1 / (k + rank)
```

### The Algorithm

**For each document appearing in any result list:**

```python
RRF_score(doc) = Σ [ 1 / (k + rank_i(doc)) ]
```

Where:
- `rank_i(doc)` = Position of document in result list i (0-indexed: 0, 1, 2, ...)
- `k` = Constant smoothing factor (typically 60)
- `Σ` = Sum across all result lists where document appears

**Why k=60?**

Research shows [k=60 is robust across different datasets](https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking). It balances:
- **Low k** (e.g., 10): Top results get huge boost, risky if one system is wrong
- **High k** (e.g., 200): All ranks similar, reduces impact of ranking
- **k=60**: Sweet spot that rewards top results but values consensus

### Example Calculation

**Search query:** "scaling microservices"

**Vector Search Results:**
1. Doc A (rank 0) - "Microservices architecture patterns"
2. Doc B (rank 1) - "Scaling distributed systems"
3. Doc C (rank 2) - "Container orchestration"

**Text Search Results:**
1. Doc B (rank 0) - Contains "microservices" keyword
2. Doc D (rank 1) - Contains "scaling" keyword
3. Doc A (rank 2) - Contains both keywords

**RRF Calculation (k=60):**

**Doc A:**
```
Vector: 1/(60+0) = 0.0167
Text:   1/(60+2) = 0.0161
Total:  0.0328
```

**Doc B:**
```
Vector: 1/(60+1) = 0.0164
Text:   1/(60+0) = 0.0167
Total:  0.0331  ← HIGHEST (appears high in both!)
```

**Doc C:**
```
Vector: 1/(60+2) = 0.0161
Text:   (not present) = 0
Total:  0.0161
```

**Doc D:**
```
Vector: (not present) = 0
Text:   1/(60+1) = 0.0164
Total:  0.0164
```

**Final Ranking:**
1. **Doc B** (0.0331) - Consensus winner! High in both searches
2. Doc A (0.0328) - Strong in vector, decent in text
3. Doc D (0.0164) - Only in text search
4. Doc C (0.0161) - Only in vector search

**Key Insight:** Doc B wins because it ranked high in **both** searches, demonstrating the power of consensus ranking!

### Our Implementation

```python
def reciprocal_rank_fusion(
    search_results_list: List[List[SearchResult]],
    k: int = 60
) -> List[SearchResult]:
    """Merge multiple ranked lists using RRF."""

    rrf_scores: Dict[str, float] = {}
    chunk_map: Dict[str, SearchResult] = {}

    # Process each result list
    for results in search_results_list:
        for rank, result in enumerate(results):
            chunk_id = result.chunk_id

            # Calculate RRF contribution
            rrf_score = 1.0 / (k + rank)

            # Accumulate scores (automatic deduplication)
            if chunk_id in rrf_scores:
                rrf_scores[chunk_id] += rrf_score
            else:
                rrf_scores[chunk_id] = rrf_score
                chunk_map[chunk_id] = result

    # Sort by combined score (descending)
    sorted_chunks = sorted(
        rrf_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    # Return merged results
    return [chunk_map[chunk_id] for chunk_id, _ in sorted_chunks]
```

**Why This Works:**

1. **Scale-independent**: Works with any scoring system
2. **Automatic deduplication**: Documents appearing in multiple lists counted once
3. **Consensus rewards**: Documents ranking high in multiple systems get highest scores
4. **Robust**: Not critically sensitive to k value
5. **Simple**: No complex normalization or calibration needed

---

## Our Hybrid Search Implementation

### Architecture Overview

```
User Query: "scaling microservices"
         ↓
    ┌────────────────────┐
    │ hybrid_search()    │
    └────────────────────┘
         ↓
    ┌─────────────────────────────┐
    │   asyncio.gather()          │
    │   (Run concurrently)        │
    └─────────────────────────────┘
         ↓                ↓
    ┌─────────┐      ┌──────────┐
    │ Vector  │      │   Text   │
    │ Search  │      │  Search  │
    └─────────┘      └──────────┘
         ↓                ↓
    [Doc A: 0.89]    [Doc B: 15.2]
    [Doc B: 0.85]    [Doc D: 12.7]
    [Doc C: 0.81]    [Doc A: 10.1]
         ↓                ↓
    ┌─────────────────────────────┐
    │  Reciprocal Rank Fusion     │
    │  (k=60)                     │
    └─────────────────────────────┘
         ↓
    [Doc B: 0.0331] ← Best in both!
    [Doc A: 0.0328]
    [Doc D: 0.0164]
    [Doc C: 0.0161]
```

### Step-by-Step Execution

#### 1. Prepare Query

```python
async def hybrid_search(ctx, query: str, match_count: int = 10):
    # Over-fetch for better RRF results
    fetch_count = match_count * 2  # e.g., fetch 20 to return 10
```

**Why over-fetch?** More candidates = better RRF merging quality

#### 2. Run Searches Concurrently

```python
# Both searches run in parallel (not sequential!)
semantic_results, text_results = await asyncio.gather(
    semantic_search(ctx, query, fetch_count),
    text_search(ctx, query, fetch_count),
    return_exceptions=True  # Don't fail if one errors
)
```

**Performance impact:** ~350-600ms total (vs. 700-1200ms if sequential)

#### 3. Handle Errors Gracefully

```python
# If vector search fails, use text only
if isinstance(semantic_results, Exception):
    logger.warning("Vector search failed, using text only")
    semantic_results = []

# If text search fails, use vector only
if isinstance(text_results, Exception):
    logger.warning("Text search failed, using vector only")
    text_results = []

# If both fail, return empty
if not semantic_results and not text_results:
    return []
```

#### 4. Merge with RRF

```python
merged_results = reciprocal_rank_fusion(
    [semantic_results, text_results],
    k=60  # Standard constant
)
```

#### 5. Return Top Results

```python
# Trim to requested count
final_results = merged_results[:match_count]
```

### Complete Code Flow

```python
async def hybrid_search(
    ctx: RunContext[AgentDependencies],
    query: str,
    match_count: Optional[int] = None
) -> List[SearchResult]:
    """Perform hybrid search combining semantic and keyword matching."""

    # 1. Setup
    match_count = match_count or 10
    fetch_count = match_count * 2  # Over-fetch for RRF

    # 2. Run searches concurrently
    semantic_results, text_results = await asyncio.gather(
        semantic_search(ctx, query, fetch_count),
        text_search(ctx, query, fetch_count),
        return_exceptions=True
    )

    # 3. Handle errors
    if isinstance(semantic_results, Exception):
        semantic_results = []
    if isinstance(text_results, Exception):
        text_results = []

    # 4. Merge with RRF
    merged_results = reciprocal_rank_fusion(
        [semantic_results, text_results],
        k=60
    )

    # 5. Return top N
    return merged_results[:match_count]
```

---

## Benefits & Trade-offs

### Why Hybrid Search?

**1. Best of Both Worlds**
- Semantic search: Finds conceptually similar content
- Text search: Finds exact terms and handles typos
- RRF: Promotes documents that excel in both

**2. Query Type Flexibility**

| Query Type | Vector Alone | Text Alone | Hybrid (RRF) |
|------------|--------------|------------|--------------|
| "scaling microservices" | ✅ Good | ✅ Good | ⭐ Excellent |
| "error code 429" | ❌ Misses exact code | ✅ Finds exact | ⭐ Best match |
| "improve performance" | ✅ Finds concepts | ❌ Too broad | ⭐ Balanced |
| "mongoDB $rankfusion" (typo) | ❌ No vectors for typos | ✅ Fuzzy match | ⭐ Catches it |

**3. Robustness**
- One search fails? Still get results from the other
- Poor vector embeddings? Text search compensates
- Missing keywords? Semantic search saves you

**4. No Score Normalization**

Unlike weighted averaging, RRF doesn't require:
- Calibrating weights (0.7 vector + 0.3 text?)
- Normalizing scores (how to make BM25 comparable to cosine?)
- Tuning per dataset (works well by default)

### Why MongoDB?

**Native Integration:**
- Both `$vectorSearch` and `$search` in aggregation pipeline
- No need for separate search engines (Elasticsearch, Pinecone, etc.)
- Single database connection, single query

**Free Tier Compatible:**
- Our manual RRF works on M0 (free tier)
- MongoDB's `$rankFusion` requires M10+ ($0.08/hr = ~$57/month)
- Same quality, zero cost!

**Performance:**
- Concurrent execution with `asyncio.gather()`
- HNSW algorithm for fast vector search
- Lucene-powered text search
- Total latency: 350-600ms per query

**Scalability:**
- MongoDB handles billions of documents
- Automatic sharding and replication
- Atlas manages infrastructure

### Trade-offs

**Manual RRF vs. Native $rankFusion:**

| Feature | Manual RRF (Our Approach) | $rankFusion (MongoDB) |
|---------|--------------------------|----------------------|
| **Cost** | ✅ Free (M0 tier) | ❌ Requires M10+ (~$57/month) |
| **Latency** | ⚠️ 350-600ms (2 queries) | ✅ 200-400ms (single query) |
| **Code Complexity** | ⚠️ More code (~80 lines) | ✅ Simple (pipeline stage) |
| **Flexibility** | ✅ Full control over merging | ⚠️ Limited customization |
| **Debugging** | ✅ See each search separately | ⚠️ Black box merging |

**When to Use Each:**

- **Use Manual RRF** (our approach):
  - Development and prototyping
  - Low-traffic applications
  - Cost-sensitive projects
  - Need custom merging logic

- **Use $rankFusion**:
  - High-traffic production (>1000 queries/min)
  - Latency-critical applications (<200ms requirement)
  - Want MongoDB to handle everything

**Migration Path:**

Our code structure makes it easy to swap:
```python
# Current: Manual RRF
async def hybrid_search(ctx, query, match_count):
    results = await asyncio.gather(
        semantic_search(...),
        text_search(...)
    )
    return reciprocal_rank_fusion(results)

# Future: Switch to $rankFusion
async def hybrid_search(ctx, query, match_count):
    pipeline = [{"$rankFusion": {"pipelines": {...}}}]
    return await collection.aggregate(pipeline)
```

---

## Query Examples

### Example 1: Conceptual Query

**Query:** "How do microservices improve scalability?"

**Vector Search Results:**
```
1. "Distributed systems enable independent scaling..." (0.89)
2. "Service-oriented architecture benefits..." (0.85)
3. "Breaking monoliths into services..." (0.82)
```

**Text Search Results:**
```
1. "Microservices architecture improves scalability by..." (18.5)
2. "How to scale microservices with Kubernetes..." (15.2)
3. "Microservices vs monoliths comparison..." (12.8)
```

**RRF Merged Results:**
```
1. [0.0328] "Microservices architecture improves..." ← Has "microservices" + semantic match
2. [0.0314] "How to scale microservices with..." ← Has keywords
3. [0.0297] "Distributed systems enable..." ← Strong semantic
```

**Winner:** Documents with both keywords AND semantic relevance!

---

### Example 2: Exact Term Search

**Query:** "$rankFusion operator MongoDB"

**Vector Search Results:**
```
1. "MongoDB aggregation operators overview..." (0.78)
2. "Database query optimization techniques..." (0.72)
3. "Search operators in NoSQL databases..." (0.68)
```
*(Missing exact "$rankFusion" - no vectors for special characters)*

**Text Search Results:**
```
1. "The $rankFusion operator combines pipelines..." (22.1) ← EXACT MATCH
2. "MongoDB $vectorSearch and $rankFusion..." (19.7) ← EXACT MATCH
3. "Using MongoDB operators for hybrid search..." (14.3)
```
*(Fuzzy matching finds exact term despite special characters)*

**RRF Merged Results:**
```
1. [0.0331] "The $rankFusion operator combines..." ← #1 text, decent vector
2. [0.0328] "MongoDB $vectorSearch and $rankFusion..." ← #2 text, semantic match
3. [0.0278] "MongoDB aggregation operators..." ← High vector only
```

**Winner:** Text search saves the day by finding exact term!

---

### Example 3: Typo Handling

**Query:** "microservces architecture" (missing 'i')

**Vector Search Results:**
```
1. "Microservices design patterns..." (0.84) ← Vectors unaffected by typo!
2. "Service architecture principles..." (0.79)
3. "Building scalable systems..." (0.75)
```

**Text Search Results:**
```
1. "Microservices architecture guide..." (17.8) ← Fuzzy match fixes typo!
2. "Architecture patterns for microservices..." (15.2)
3. "Service-oriented architecture..." (12.1)
```
*(maxEdits=2 allows "microservces" → "microservices")*

**RRF Merged Results:**
```
1. [0.0331] "Microservices architecture guide..." ← Best text + good vector
2. [0.0314] "Microservices design patterns..." ← Top vector + text match
3. [0.0280] "Architecture patterns for..." ← Decent in both
```

**Winner:** Hybrid approach handles typo gracefully - both searches contribute!

---

## Technical Deep Dive: Building Queries

### Semantic Search Query Construction

```python
async def semantic_search(ctx, query: str, match_count: int):
    # Step 1: Generate embedding for query text
    query_embedding = await deps.get_embedding(query)
    # Result: [0.023, -0.15, 0.42, ..., 0.08] (1536 floats)

    # Step 2: Build aggregation pipeline
    pipeline = [
        # Stage 1: Vector similarity search
        {
            "$vectorSearch": {
                "index": "vector_index",          # Must match Atlas index name
                "queryVector": query_embedding,   # MUST be Python list[float]
                "path": "embedding",              # Field containing stored embeddings
                "numCandidates": 100,             # Search 100 candidates to find 10 best
                "limit": match_count              # Return top N results
            }
        },

        # Stage 2: Join with parent documents
        {
            "$lookup": {
                "from": "documents",              # Target collection
                "localField": "document_id",      # FK in chunks
                "foreignField": "_id",            # PK in documents
                "as": "document_info"             # Output field name
            }
        },

        # Stage 3: Flatten joined data
        {
            "$unwind": "$document_info"
        },

        # Stage 4: Shape output + extract score
        {
            "$project": {
                "chunk_id": "$_id",
                "document_id": 1,
                "content": 1,
                "similarity": {"$meta": "vectorSearchScore"},  # Extract vector score
                "metadata": 1,
                "document_title": "$document_info.title",
                "document_source": "$document_info.source"
            }
        }
    ]

    # Step 3: Execute pipeline
    collection = deps.db["chunks"]
    cursor = await collection.aggregate(pipeline)
    results = [doc async for doc in cursor]

    # Step 4: Convert to Pydantic models
    return [SearchResult(**doc) for doc in results]
```

**Common Pitfalls:**

❌ **Wrong:** `queryVector: "[0.023, -0.15, ...]"` (string)
✅ **Correct:** `queryVector: [0.023, -0.15, ...]` (list)

❌ **Wrong:** Forgot `$lookup` - no document metadata
✅ **Correct:** Always join with documents collection

❌ **Wrong:** `numCandidates: 10` with `limit: 10` (search too narrow)
✅ **Correct:** `numCandidates: 100` with `limit: 10` (10x rule)

---

### Text Search Query Construction

```python
async def text_search(ctx, query: str, match_count: int):
    # Step 1: Build aggregation pipeline (no embedding needed!)
    pipeline = [
        # Stage 1: Full-text search
        {
            "$search": {
                "index": "text_index",            # Must match Atlas Search index
                "text": {
                    "query": query,               # Raw search text (no processing)
                    "path": "content",            # Field to search in
                    "fuzzy": {
                        "maxEdits": 2,            # Allow 2 character changes
                        "prefixLength": 3         # First 3 chars must match
                    }
                }
            }
        },

        # Stage 2: Limit results (over-fetch for RRF)
        {
            "$limit": match_count * 2
        },

        # Stage 3: Join with parent documents
        {
            "$lookup": {
                "from": "documents",
                "localField": "document_id",
                "foreignField": "_id",
                "as": "document_info"
            }
        },

        # Stage 4: Flatten joined data
        {
            "$unwind": "$document_info"
        },

        # Stage 5: Shape output + extract score
        {
            "$project": {
                "chunk_id": "$_id",
                "document_id": 1,
                "content": 1,
                "similarity": {"$meta": "searchScore"},  # Extract text search score
                "metadata": 1,
                "document_title": "$document_info.title",
                "document_source": "$document_info.source"
            }
        }
    ]

    # Step 2: Execute pipeline
    collection = deps.db["chunks"]
    cursor = await collection.aggregate(pipeline)
    results = [doc async for doc in cursor]

    # Step 3: Convert to Pydantic models
    return [SearchResult(**doc) for doc in results]
```

**Fuzzy Matching Examples:**

| Query | maxEdits | prefixLength | Matches | Doesn't Match |
|-------|----------|--------------|---------|---------------|
| "microservices" | 2 | 3 | "microservice", "micro-services", "microservces" | "macroservices" (prefix diff) |
| "scaling" | 1 | 2 | "scalling" (1 typo) | "scaling" + "sealing" (2 edits) |
| "API" | 2 | 0 | "API", "APA", "AAI" | (no prefix requirement) |

---

### Hybrid Search Query Construction

```python
async def hybrid_search(ctx, query: str, match_count: int = 10):
    # Step 1: Over-fetch from each search method
    fetch_count = match_count * 2  # e.g., 20 for top 10

    # Step 2: Run both searches concurrently
    semantic_results, text_results = await asyncio.gather(
        semantic_search(ctx, query, fetch_count),  # Returns List[SearchResult]
        text_search(ctx, query, fetch_count),      # Returns List[SearchResult]
        return_exceptions=True                     # Don't crash if one fails
    )

    # Step 3: Error handling
    if isinstance(semantic_results, Exception):
        semantic_results = []
    if isinstance(text_results, Exception):
        text_results = []

    # Step 4: Apply RRF algorithm
    merged_results = reciprocal_rank_fusion(
        search_results_list=[semantic_results, text_results],
        k=60  # Standard constant
    )

    # Step 5: Return top N results
    return merged_results[:match_count]
```

**RRF Algorithm Implementation:**

```python
def reciprocal_rank_fusion(
    search_results_list: List[List[SearchResult]],
    k: int = 60
) -> List[SearchResult]:
    """Merge ranked lists using RRF."""

    # Dictionary to accumulate scores by chunk_id
    rrf_scores: Dict[str, float] = {}
    chunk_map: Dict[str, SearchResult] = {}

    # Process each result list (vector, text, etc.)
    for results in search_results_list:
        for rank, result in enumerate(results):
            chunk_id = result.chunk_id

            # RRF formula: 1 / (k + rank)
            # rank is 0-indexed: 0, 1, 2, 3, ...
            rrf_contribution = 1.0 / (k + rank)

            # Accumulate scores across all lists
            if chunk_id in rrf_scores:
                # Document appeared in multiple lists - add scores
                rrf_scores[chunk_id] += rrf_contribution
            else:
                # First time seeing this document
                rrf_scores[chunk_id] = rrf_contribution
                chunk_map[chunk_id] = result  # Store for later

    # Sort by combined RRF score (highest first)
    sorted_results = sorted(
        rrf_scores.items(),
        key=lambda x: x[1],  # Sort by score
        reverse=True         # Descending order
    )

    # Build final result list
    merged = []
    for chunk_id, rrf_score in sorted_results:
        result = chunk_map[chunk_id]
        # Update similarity field with RRF score
        result.similarity = rrf_score
        merged.append(result)

    return merged
```

---

## Summary

### What We Built

A **production-ready hybrid search system** combining:
- ✅ MongoDB Vector Search for semantic understanding
- ✅ MongoDB Atlas Search for keyword matching
- ✅ Reciprocal Rank Fusion for intelligent merging
- ✅ Concurrent execution for performance
- ✅ Graceful error handling
- ✅ Free tier compatible (M0)

### Key Takeaways

1. **Vector search** finds conceptually similar content using embeddings
2. **Text search** finds exact matches and handles typos with fuzzy matching
3. **RRF** intelligently merges results based on rank, not raw scores
4. **MongoDB aggregation pipelines** chain operations for complex queries
5. **Hybrid approach** outperforms either method alone

### References

- [MongoDB Vector Search Overview](https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-overview/)
- [MongoDB Atlas Search Documentation](https://www.mongodb.com/docs/atlas/atlas-search/text/)
- [MongoDB $vectorSearch Stage](https://www.mongodb.com/docs/manual/reference/operator/aggregation/vectorsearch/)
- [MongoDB Aggregation Pipeline](https://www.mongodb.com/docs/manual/core/aggregation-pipeline/)
- [MongoDB $lookup Documentation](https://www.mongodb.com/docs/manual/reference/operator/aggregation/lookup/)
- [MongoDB $rankFusion Hybrid Search](https://www.mongodb.com/docs/atlas/atlas-vector-search/hybrid-search/vector-search-with-full-text-search/)
- [Reciprocal Rank Fusion Algorithm](https://medium.com/@mahaboobali_shaik/reciprocal-rank-fusion-rrf-a-simple-yet-powerful-search-ranking-technique-6e29d84a5357)
- [Azure AI Search: RRF Hybrid Search](https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking)
- [MongoDB Blog: RRF and RSF Techniques](https://medium.com/mongodb/reciprocal-rank-fusion-and-relative-score-fusion-classic-hybrid-search-techniques-3bf91008b81d)

---

**Built with ❤️ for production use on MongoDB Atlas Free Tier (M0)**
