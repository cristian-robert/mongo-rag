# MongoDB Hybrid Search Explained

**Quick Guide:** How we combine semantic understanding with keyword precision using MongoDB Atlas Vector Search, Text Search, and Reciprocal Rank Fusion.

---

## The Problem

Traditional search has a fundamental trade-off:
- **Keyword search** → Finds exact terms but misses concepts
- **Semantic search** → Understands meaning but misses specific terms

**Example:** "scaling microservices" should find both:
- "distributed systems patterns" (concept)
- Exact term "microservices" (keyword)

## The Solution: Hybrid Search

Combine three MongoDB features:
1. **$vectorSearch** - Semantic similarity via embeddings
2. **$search** - Keyword matching with fuzzy typo handling
3. **RRF Algorithm** - Smart merging of both results

**Cost:** Free on M0 tier! 🎉

---

## 1. Vector Search ($vectorSearch)

**What:** Finds semantically similar content using embeddings (numbers representing meaning)

**How:**
```python
# Text → 1536 numbers representing meaning
"scaling microservices" → [0.023, -0.15, 0.42, ..., 0.08]

# MongoDB finds similar vectors using cosine similarity
{
    "$vectorSearch": {
        "index": "vector_index",
        "queryVector": [0.023, -0.15, ...],  # Must be list, not string!
        "path": "embedding",
        "numCandidates": 100,  # Search space (10x your limit)
        "limit": 10
    }
}
```

**Returns:** Score 0-1 (0 = different, 1 = identical)

**Strength:** Finds "distributed systems patterns" when you search "microservices"

---

## 2. Text Search ($search)

**What:** Keyword matching with fuzzy typo handling (powered by Apache Lucene)

**How:**
```python
{
    "$search": {
        "index": "text_index",
        "text": {
            "query": "microservces",  # Typo!
            "path": "content",
            "fuzzy": {
                "maxEdits": 2,      # Allow 2 character changes
                "prefixLength": 3   # First 3 chars must match
            }
        }
    }
}
```

**Fuzzy matching fixes:**
- "microservces" → "microservices" ✓
- "micro-services" → "microservices" ✓
- "microservies" → "microservices" ✓

**Strength:** Finds exact terms and handles typos

---

## 3. Aggregation Pipeline (How Data Transforms)

**Think Unix pipes:** `cat file | grep | sort | head`

MongoDB pipelines work the same way - each stage transforms documents and passes them forward.

### Stage 1: $vectorSearch (Entry Point)

**MUST be the first stage in your pipeline!**

```python
{
    "$vectorSearch": {
        "index": "vector_index",
        "queryVector": [0.023, -0.15, ...],  # 1536 floats
        "path": "embedding",
        "numCandidates": 100,
        "limit": 10
    }
}
```

**Output:** Top 10 chunks by similarity
```javascript
{
  "_id": ObjectId("abc123"),
  "document_id": ObjectId("doc456"),
  "content": "Microservices enable independent scaling...",
  "embedding": [0.021, -0.14, ...],
  // No similarity score yet! Need $project to extract it
}
```

### Stage 2: $lookup (Join Collections)

**Joins chunks with their parent documents to get metadata (title, source)**

```python
{
    "$lookup": {
        "from": "documents",         # Collection to join with
        "localField": "document_id", # FK in chunks
        "foreignField": "_id",       # PK in documents
        "as": "document_info"        # Output field name
    }
}
```

**Data transformation:**
```javascript
// BEFORE $lookup
{
  "_id": ObjectId("abc123"),
  "document_id": ObjectId("doc456"),
  "content": "Microservices enable..."
}

// AFTER $lookup (added document_info array)
{
  "_id": ObjectId("abc123"),
  "document_id": ObjectId("doc456"),
  "content": "Microservices enable...",
  "document_info": [{                    // ← New array with joined data
    "_id": ObjectId("doc456"),
    "title": "Architecture Guide",
    "source": "arch-guide.pdf",
    "created_at": ISODate("2024-01-15")
  }]
}
```

### Stage 3: $unwind (Flatten Arrays)

**Converts the document_info array into a single object**

```python
{"$unwind": "$document_info"}
```

**Data transformation:**
```javascript
// BEFORE $unwind (document_info is an array)
{
  "content": "Microservices enable...",
  "document_info": [{
    "title": "Architecture Guide",
    "source": "arch-guide.pdf"
  }]
}

// AFTER $unwind (document_info is now an object)
{
  "content": "Microservices enable...",
  "document_info": {              // ← No longer an array!
    "title": "Architecture Guide",
    "source": "arch-guide.pdf"
  }
}
```

**Why this matters:** Now we can access `document_info.title` directly instead of `document_info[0].title`

### Stage 4: $project (Shape Output + Extract Scores)

**Selects which fields to return and extracts the search score**

```python
{
    "$project": {
        "chunk_id": "$_id",                           # Rename _id
        "document_id": 1,                             # Include as-is (1 = include)
        "content": 1,                                 # Include as-is
        "similarity": {"$meta": "vectorSearchScore"}, # Extract score!
        "metadata": 1,                                # Include as-is
        "document_title": "$document_info.title",     # Extract nested field
        "document_source": "$document_info.source"    # Extract nested field
    }
}
```

**Data transformation:**
```javascript
// BEFORE $project (all fields, nested structure)
{
  "_id": ObjectId("abc123"),
  "document_id": ObjectId("doc456"),
  "content": "Microservices enable...",
  "embedding": [0.021, -0.14, ...],      // ← Don't need this anymore
  "metadata": {"chunk_index": 0},
  "document_info": {
    "title": "Architecture Guide",
    "source": "arch-guide.pdf",
    "created_at": ISODate("2024-01-15")  // ← Don't need this
  }
}

// AFTER $project (clean, flat structure)
{
  "chunk_id": "abc123",                      // ← Renamed from _id
  "document_id": "doc456",
  "content": "Microservices enable...",
  "similarity": 0.87,                        // ← Extracted from metadata!
  "metadata": {"chunk_index": 0},
  "document_title": "Architecture Guide",    // ← Flattened from nested
  "document_source": "arch-guide.pdf"        // ← Flattened from nested
}
```

**Special $meta expressions:**
- `{"$meta": "vectorSearchScore"}` - Score from `$vectorSearch` (0-1 range)
- `{"$meta": "searchScore"}` - Score from `$search` (varies by relevance)

### Complete Pipeline Example

```python
pipeline = [
    # Stage 1: Find similar vectors
    {
        "$vectorSearch": {
            "index": "vector_index",
            "queryVector": query_embedding,
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

    # Stage 3: Flatten the document_info array
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

# Execute
results = await db.chunks.aggregate(pipeline).to_list(length=10)
```

**Final output:**
```python
[
    {
        "chunk_id": "abc123",
        "document_id": "doc456",
        "content": "Microservices architecture enables independent scaling...",
        "similarity": 0.87,
        "document_title": "Architecture Guide",
        "document_source": "arch-guide.pdf"
    },
    # ... 9 more results
]
```

---

## 4. Reciprocal Rank Fusion (RRF)

**Problem:** Vector search returns 0.85, text search returns 15.2 - how to combine different scales?

**Solution:** Use **rank position** (1st, 2nd, 3rd), not raw scores!

**Formula:**
```python
RRF_score = 1 / (60 + rank)  # k=60 is industry standard
```

**Example:**
```
Query: "scaling microservices"

Vector Results:          Text Results:
1. Doc A (rank 0)        1. Doc B (rank 0)
2. Doc B (rank 1)        2. Doc D (rank 1)
3. Doc C (rank 2)        3. Doc A (rank 2)

RRF Scores:
Doc B: 1/(60+1) + 1/(60+0) = 0.0331 ← WINNER (high in BOTH!)
Doc A: 1/(60+0) + 1/(60+2) = 0.0328
Doc D: 0 + 1/(60+1) = 0.0164
Doc C: 1/(60+2) + 0 = 0.0161
```

**Why it works:**
- ✅ Scale-independent (works with any scoring system)
- ✅ Auto-deduplication (documents in multiple lists counted once)
- ✅ Rewards consensus (high in both searches = best score)
- ✅ Simple (no normalization needed)

---

## 5. Our Implementation

**Flow:**
```
Query → [Vector Search + Text Search] → RRF Merge → Top Results
        (concurrent, ~400ms total)
```

**Code:**
```python
async def hybrid_search(ctx, query: str, match_count: int = 10):
    # 1. Over-fetch (2x) for better RRF quality
    fetch_count = match_count * 2

    # 2. Run both searches concurrently (not sequential!)
    semantic_results, text_results = await asyncio.gather(
        semantic_search(ctx, query, fetch_count),
        text_search(ctx, query, fetch_count),
        return_exceptions=True  # Graceful degradation
    )

    # 3. Handle errors (one search can fail, still get results)
    if isinstance(semantic_results, Exception):
        semantic_results = []
    if isinstance(text_results, Exception):
        text_results = []

    # 4. Merge with RRF
    merged = reciprocal_rank_fusion([semantic_results, text_results], k=60)

    # 5. Return top N
    return merged[:match_count]
```

---

## Why This Approach?

**Query Performance:**

| Query Type | Vector Only | Text Only | Hybrid (RRF) |
|------------|------------|-----------|--------------|
| Conceptual ("scaling patterns") | ✅ Good | ❌ Misses | ⭐ Best |
| Exact terms ("error 429") | ❌ Misses | ✅ Good | ⭐ Best |
| With typos ("microservces") | ❌ Fails | ✅ Catches | ⭐ Best |

**Benefits:**
- ✅ **Robustness** - One search fails? Other still works
- ✅ **No tuning** - No weights to calibrate, works by default
- ✅ **Free tier** - Runs on MongoDB M0 (vs. $rankFusion needing M10+)
- ✅ **Fast** - Concurrent execution: ~400ms total

**Trade-off:**
- Manual RRF: Free, more code, full control
- MongoDB $rankFusion: Faster (~200ms), paid tier, less flexible

---

## Quick Reference: Common Patterns

**Vector search must-knows:**
```python
# ✅ Correct: Python list
queryVector: [0.023, -0.15, ...]

# ❌ Wrong: String
queryVector: "[0.023, -0.15, ...]"

# ✅ Rule: numCandidates = 10x limit
numCandidates: 100, limit: 10
```

**Fuzzy matching examples:**
```python
# maxEdits=2, prefixLength=3
"microservces" → "microservices" ✓  (1 typo)
"microservice" → "microservices" ✓  (1 char)
"macroservices" → "microservices" ✗ (prefix differs)
```

**Pipeline stages order:**
```python
1. $vectorSearch or $search  # MUST be first!
2. $lookup                   # Join collections
3. $unwind                   # Flatten arrays
4. $project                  # Shape + extract scores
```

---

## References

**MongoDB Docs:**
- [Vector Search Overview](https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-overview/)
- [Atlas Search (Text)](https://www.mongodb.com/docs/atlas/atlas-search/text/)
- [$vectorSearch Stage](https://www.mongodb.com/docs/manual/reference/operator/aggregation/vectorsearch/)
- [Aggregation Pipeline](https://www.mongodb.com/docs/manual/core/aggregation-pipeline/)
- [$rankFusion Hybrid Search](https://www.mongodb.com/docs/atlas/atlas-vector-search/hybrid-search/vector-search-with-full-text-search/)

**RRF Algorithm:**
- [RRF Explained (Medium)](https://medium.com/@mahaboobali_shaik/reciprocal-rank-fusion-rrf-a-simple-yet-powerful-search-ranking-technique-6e29d84a5357)
- [Azure AI RRF Guide](https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking)
- [MongoDB RRF Blog](https://medium.com/mongodb/reciprocal-rank-fusion-and-relative-score-fusion-classic-hybrid-search-techniques-3bf91008b81d)

---

**Built for MongoDB Atlas Free Tier (M0)** 🚀
