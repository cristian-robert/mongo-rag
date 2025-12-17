# Feature: Phase 3 - Agent, Search Tools & CLI

## Feature Description

Build complete conversational RAG agent combining MongoDB search tools with Pydantic AI agent framework and Rich CLI interface. This integrated implementation adapts the PostgreSQL reference (examples/) to MongoDB, changing only database operations while preserving the proven agent/CLI architecture.

## User Story

As a **user of the MongoDB RAG system**
I want to **ask questions conversationally and get intelligent answers from my knowledge base**
So that **I can quickly find information without manual searching or learning query syntax**

## Problem Statement

Need to implement the complete user-facing system:
1. MongoDB-specific search tools (`$vectorSearch` + `$rankFusion` aggregations)
2. Pydantic AI agent that orchestrates search tool calls
3. Rich CLI with streaming responses and tool call visibility
4. Conversation history and context management
5. Type-safe results with source attribution

## Solution Statement

Create integrated agent system by adapting examples/ to MongoDB:
- **src/tools.py**: Replace PostgreSQL functions with MongoDB aggregation pipelines
- **src/agent.py**: Copy agent structure, update imports to src.*
- **src/cli.py**: Copy CLI interface, update imports to src.*
- **src/prompts.py**: Copy system prompts directly (platform-agnostic)

Architecture: User → CLI → Agent → Search Tool → MongoDB Aggregation → Results → LLM → Streaming Response

## Feature Metadata

**Feature Type**: Core Feature (User-Facing System)
**Estimated Complexity**: Medium-High
**Primary Systems Affected**: Search, Agent, User Interface
**Dependencies**: Phase 2 complete, MongoDB indexes created in Atlas UI

---

## CONTEXT REFERENCES

### Relevant Codebase Files (READ BEFORE IMPLEMENTING!)

**Examples (PostgreSQL Reference):**
- `examples/tools.py` (1-150) - PostgreSQL search patterns, SearchResult model
- `examples/agent.py` (1-133) - Pydantic AI agent setup, StateDeps pattern
- `examples/cli.py` (1-260) - Rich CLI with streaming, tool call visibility
- `examples/prompts.py` (1-36) - System prompts (copy as-is)

**Existing Src:**
- `src/dependencies.py` (1-127) - MongoDB AgentDependencies already built
- `src/settings.py` (1-105) - MongoDB configuration
- `src/providers.py` (1-81) - LLM/embedding providers

**Reference Docs:**
- `.claude/reference/mongodb-patterns.md` (1-514) - MongoDB aggregation pipelines
- `.claude/reference/agent-tools.md` - Pydantic AI patterns
- `CLAUDE.md` (1-300) - TYPE SAFETY, ASYNC, Google docstrings

### Key Documentation

- [MongoDB $vectorSearch](https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-stage/) - Vector search aggregation stage
- [MongoDB $rankFusion](https://www.mongodb.com/docs/atlas/atlas-vector-search/hybrid-search/vector-search-with-full-text-search/) - Hybrid search operator
- [Pydantic AI Agents](https://ai.pydantic.dev/agents/) - Agent framework docs
- [Pydantic AI Tools](https://ai.pydantic.dev/tools/) - Tool registration patterns

### Critical Patterns

**MongoDB Vector Search Pipeline:**
```python
pipeline = [
    {
        "$vectorSearch": {
            "index": "vector_index",
            "queryVector": query_embedding,  # list[float], NOT string!
            "path": "embedding",
            "numCandidates": 100,
            "limit": match_count
        }
    },
    {
        "$lookup": {
            "from": "documents",
            "localField": "document_id",
            "foreignField": "_id",
            "as": "document_info"
        }
    },
    {
        "$unwind": "$document_info"
    },
    {
        "$project": {
            "chunk_id": "$_id",
            "document_id": 1,
            "content": 1,
            "similarity": {"$meta": "vectorSearchScore"},
            "metadata": 1,
            "document_title": "$document_info.title",
            "document_source": "$document_info.source"
        }
    }
]

results = await db.chunks.aggregate(pipeline).to_list(length=match_count)
```

**MongoDB Hybrid Search ($rankFusion):**
```python
pipeline = [
    {
        "$rankFusion": {
            "input": {
                "pipelines": {
                    "semantic": [
                        {
                            "$vectorSearch": {
                                "index": "vector_index",
                                "queryVector": query_embedding,
                                "path": "embedding",
                                "numCandidates": 100,
                                "limit": match_count
                            }
                        }
                    ],
                    "fulltext": [
                        {
                            "$search": {
                                "index": "text_index",
                                "text": {
                                    "query": query,
                                    "path": "content",
                                    "fuzzy": {"maxEdits": 1}
                                }
                            }
                        },
                        {"$limit": match_count}
                    ]
                }
            }
        }
    },
    {
        "$lookup": {
            "from": "documents",
            "localField": "document_id",
            "foreignField": "_id",
            "as": "document_info"
        }
    },
    {
        "$unwind": "$document_info"
    },
    {
        "$project": {
            "chunk_id": "$_id",
            "document_id": 1,
            "content": 1,
            "combined_score": {"$meta": "rankFusionScore"},
            "metadata": 1,
            "document_title": "$document_info.title",
            "document_source": "$document_info.source"
        }
    }
]
```

**Pydantic AI Tool Pattern:**
```python
@rag_agent.tool
async def search_knowledge_base(
    ctx: RunContext[StateDeps[RAGState]],
    query: str,
    match_count: Optional[int] = 5,
    search_type: Optional[str] = "hybrid"
) -> str:
    """Search knowledge base - returns formatted string for LLM."""
    # Initialize deps
    agent_deps = AgentDependencies()
    await agent_deps.initialize()

    # Call search function
    results = await hybrid_search(ctx=deps_ctx, query=query, match_count=match_count)

    # Cleanup
    await agent_deps.cleanup()

    # Format as string
    return format_results(results)
```

---

## IMPLEMENTATION PLAN

### Part 1: Search Tools (src/tools.py)
Create MongoDB search functions adapting PostgreSQL patterns to aggregation pipelines

### Part 2: Agent Setup (src/agent.py)
Copy Pydantic AI agent structure, adapt imports to src.*

### Part 3: CLI Interface (src/cli.py)
Copy Rich CLI with streaming, adapt imports to src.*

### Part 4: System Prompts (src/prompts.py)
Copy prompts directly (platform-agnostic)

### Part 5: Integration Testing
End-to-end validation with real MongoDB data

---

## STEP-BY-STEP TASKS

### CREATE src/tools.py - Part 1: SearchResult Model

- **IMPLEMENT**: Pydantic model for type-safe search results
- **PATTERN**: examples/tools.py (11-19)
- **IMPORTS**: `from pydantic import BaseModel, Field; from typing import Dict, Any`
- **MODEL FIELDS**:
  - `chunk_id: str` - MongoDB ObjectId as string
  - `document_id: str` - Parent document ObjectId
  - `content: str` - Chunk text
  - `similarity: float` - Relevance score (0-1)
  - `metadata: Dict[str, Any]` - Chunk metadata
  - `document_title: str` - From $lookup join
  - `document_source: str` - From $lookup join
- **GOTCHA**: Convert ObjectId to string with `str(obj_id)`
- **VALIDATE**: `uv run python -c "from src.tools import SearchResult; print('✓')"`

### CREATE src/tools.py - Part 2: Semantic Search Function

- **IMPLEMENT**: `async def semantic_search()` with MongoDB $vectorSearch aggregation
- **PATTERN**: examples/tools.py (22-79) + .claude/reference/mongodb-patterns.md (40-79)
- **IMPORTS**: `from pydantic_ai import RunContext; from src.dependencies import AgentDependencies; from pymongo.errors import OperationFailure`
- **KEY CHANGES FROM POSTGRESQL**:
  - NO embedding string conversion: `query_vector = query_embedding` (already list[float])
  - Use aggregation pipeline instead of SQL function
  - Extract score with `{"$meta": "vectorSearchScore"}`
  - Access db via `deps.db[deps.settings.mongodb_collection_chunks]`
  - Convert ObjectId fields to strings in SearchResult
- **PARAMETERS**: `ctx: RunContext[AgentDependencies], query: str, match_count: Optional[int] = None`
- **FLOW**:
  1. Get deps from ctx, use default match_count from settings
  2. Generate embedding: `query_embedding = await deps.get_embedding(query)`
  3. Build aggregation pipeline with $vectorSearch + $lookup + $project
  4. Execute: `results = await collection.aggregate(pipeline).to_list(length=match_count)`
  5. Convert to SearchResult objects (handle ObjectId → str conversion)
  6. Return list[SearchResult]
- **ERROR HANDLING**: Catch OperationFailure for missing index, return empty list
- **GOTCHA**: `queryVector` is Python list, NOT string '[1,2,3]'
- **GOTCHA**: `numCandidates` should be ~10x limit (e.g., 100 for limit=10)
- **VALIDATE**: After full implementation with integration test

### CREATE src/tools.py - Part 3: Hybrid Search Function

- **IMPLEMENT**: `async def hybrid_search()` with MongoDB $rankFusion
- **PATTERN**: examples/tools.py (82-149) + .claude/reference/mongodb-patterns.md (87-180)
- **PARAMETERS**: `ctx, query, match_count: Optional[int] = None, text_weight: Optional[float] = None`
- **KEY CHANGES FROM POSTGRESQL**:
  - Use $rankFusion operator (MongoDB 8.0+ native hybrid search)
  - Combine two pipelines: semantic ($vectorSearch) + fulltext ($search)
  - Extract combined score with `{"$meta": "rankFusionScore"}`
  - NO manual score combination - MongoDB handles RRF internally
- **FLOW**:
  1. Get deps, defaults, validate params
  2. Generate embedding for semantic pipeline
  3. Build $rankFusion pipeline with semantic + fulltext sub-pipelines
  4. Add $lookup and $project stages
  5. Execute aggregation
  6. Return list[SearchResult] with combined_score
- **GOTCHA**: $search requires separate Atlas Search index (text_index)
- **GOTCHA**: Fuzzy matching: `{"fuzzy": {"maxEdits": 1}}` for typo tolerance
- **VALIDATE**: After full implementation with integration test

### COPY examples/prompts.py → src/prompts.py

- **IMPLEMENT**: Copy entire file unchanged (platform-agnostic)
- **CONTENT**: MAIN_SYSTEM_PROMPT with instructions
- **GOTCHA**: Update reference from "PGVector" to "MongoDB" in welcome message (optional)
- **VALIDATE**: `uv run python -c "from src.prompts import MAIN_SYSTEM_PROMPT; print('✓')"`

### CREATE src/agent.py - Part 1: Imports and State

- **IMPLEMENT**: Import statements and RAGState model
- **PATTERN**: examples/agent.py (1-20)
- **IMPORTS**:
  - `from pydantic_ai import Agent, RunContext`
  - `from pydantic_ai.ag_ui import StateDeps`
  - `from pydantic import BaseModel`
  - `from typing import Optional`
  - `from src.providers import get_llm_model`
  - `from src.dependencies import AgentDependencies`
  - `from src.prompts import MAIN_SYSTEM_PROMPT`
  - `from src.tools import semantic_search, hybrid_search`
- **STATE MODEL**: `class RAGState(BaseModel): pass` (empty for now, extensible)
- **GOTCHA**: Use `src.*` imports, NOT relative imports
- **VALIDATE**: `uv run python -c "from src.agent import RAGState; print('✓')"`

### CREATE src/agent.py - Part 2: Agent Initialization

- **IMPLEMENT**: Create rag_agent instance
- **PATTERN**: examples/agent.py (23-28)
- **CODE**:
  ```python
  rag_agent = Agent(
      get_llm_model(),
      deps_type=StateDeps[RAGState],
      system_prompt=MAIN_SYSTEM_PROMPT
  )
  ```
- **GOTCHA**: Must use `StateDeps[RAGState]` not just `RAGState`
- **VALIDATE**: After full file implementation

### CREATE src/agent.py - Part 3: Search Tool Wrapper

- **IMPLEMENT**: `@rag_agent.tool` decorated function
- **PATTERN**: examples/agent.py (31-103)
- **FUNCTION SIGNATURE**: `async def search_knowledge_base(ctx: RunContext[StateDeps[RAGState]], query: str, match_count: Optional[int] = 5, search_type: Optional[str] = "hybrid") -> str`
- **FLOW**:
  1. Try block with exception handling
  2. Create AgentDependencies instance
  3. Initialize: `await agent_deps.initialize()`
  4. Create context wrapper for search tools
  5. Call semantic_search or hybrid_search based on search_type
  6. Cleanup: `await agent_deps.cleanup()`
  7. Format results as string for LLM
  8. Return formatted response
- **FORMATTING**: Include doc count, title, relevance score, content for each result
- **ERROR HANDLING**: Return error message string if search fails
- **GOTCHA**: Must cleanup dependencies in try/finally
- **GOTCHA**: Return type is `str` (LLM reads this), not SearchResult objects
- **VALIDATE**: After full file implementation

### CREATE src/agent.py - Part 4: Dynamic Instructions

- **IMPLEMENT**: `@rag_agent.instructions` decorated function
- **PATTERN**: examples/agent.py (105-132)
- **OPTIONAL**: Can rely on MAIN_SYSTEM_PROMPT or add dynamic instructions
- **FOR NOW**: Skip this (MAIN_SYSTEM_PROMPT is sufficient)
- **VALIDATE**: Full agent works without dynamic instructions

### CREATE src/cli.py - Part 1: Imports and Console Setup

- **IMPLEMENT**: Copy imports and Rich console setup
- **PATTERN**: examples/cli.py (1-28)
- **IMPORTS**: Update `from agent import` and `from settings import` to `from src.agent import` and `from src.settings import`
- **GOTCHA**: Remove `sys.path.insert` lines (not needed with proper package structure)
- **VALIDATE**: `uv run python -c "from src.cli import console; print('✓')"`

### CREATE src/cli.py - Part 2: Streaming Agent Interaction

- **IMPLEMENT**: `async def stream_agent_interaction()` and `async def _stream_agent()`
- **PATTERN**: examples/cli.py (31-164)
- **COPY**: Both functions unchanged, just update import references
- **KEY FEATURES**:
  - Handles PartStartEvent and PartDeltaEvent for streaming
  - Shows tool calls with FunctionToolCallEvent
  - Displays query, search_type, match_count from tool args
  - Returns (response_text, new_messages) tuple
- **GOTCHA**: Must handle node types: user_prompt, model_request, call_tools, end
- **VALIDATE**: After full file implementation

### CREATE src/cli.py - Part 3: Welcome Display

- **IMPLEMENT**: `def display_welcome()`
- **PATTERN**: examples/cli.py (167-180)
- **CHANGES**: Update "PGVector" → "MongoDB Atlas Vector Search"
- **VALIDATE**: After full file implementation

### CREATE src/cli.py - Part 4: Main Loop

- **IMPLEMENT**: `async def main()` with conversation loop
- **PATTERN**: examples/cli.py (183-260)
- **COPY**: Entire function with minimal changes
- **SPECIAL COMMANDS**:
  - `exit/quit/q` - Exit program
  - `info` - Show system configuration
  - `clear` - Clear screen and redisplay welcome
- **FLOW**:
  1. Display welcome
  2. Create RAGState and StateDeps
  3. Initialize message_history list
  4. Loop: get input → handle commands → stream interaction → update history
  5. Handle KeyboardInterrupt and exceptions gracefully
- **GOTCHA**: Message history maintains conversation context across turns
- **VALIDATE**: `uv run python -m src.cli` (full end-to-end test)

### INTEGRATION TESTING

- **VALIDATE SEARCH INDEXES**: Ensure vector_index and text_index exist in Atlas UI
- **TEST SEMANTIC SEARCH**: Run isolated test with known query
- **TEST HYBRID SEARCH**: Run isolated test comparing to semantic results
- **TEST AGENT**: Run CLI, ask simple question, verify tool call
- **TEST STREAMING**: Verify real-time response streaming
- **TEST TOOL VISIBILITY**: Verify query/type/count displayed
- **TEST CONVERSATION**: Ask follow-up question, verify context maintained
- **TEST ERROR HANDLING**: Try with missing index, verify graceful failure

---

## TESTING STRATEGY

### Unit Tests (Phase 4)
- Mock MongoDB aggregation for search functions
- Mock AgentDependencies for agent tests
- Test SearchResult model validation
- Test error handling for missing indexes

### Integration Tests
- Use test MongoDB database with sample data
- Validate search returns expected results
- Test agent tool calling logic
- Verify CLI streaming and message history

### Edge Cases
1. Empty search results - graceful "no results" message
2. Missing indexes - clear error message
3. Invalid ObjectId - proper error handling
4. Very long queries - truncation handling
5. Connection failures - retry logic
6. LLM API failures - error display in CLI

---

## VALIDATION COMMANDS

### Level 1: Imports
```bash
uv run python -c "from src.tools import SearchResult, semantic_search, hybrid_search; print('✓ tools')"
uv run python -c "from src.agent import rag_agent, RAGState; print('✓ agent')"
uv run python -c "from src.cli import console, stream_agent_interaction; print('✓ cli')"
uv run python -c "from src.prompts import MAIN_SYSTEM_PROMPT; print('✓ prompts')"
```

### Level 2: Search Functions (Isolated)
```bash
# Test semantic search with Python script
uv run python -c "
import asyncio
from src.dependencies import AgentDependencies
from src.tools import semantic_search

class MockContext:
    def __init__(self, deps):
        self.deps = deps

async def test():
    deps = AgentDependencies()
    await deps.initialize()
    ctx = MockContext(deps)
    results = await semantic_search(ctx, 'test query', match_count=5)
    print(f'✓ Semantic search: {len(results)} results')
    await deps.cleanup()

asyncio.run(test())
"
```

### Level 3: Agent Tool
```bash
# Test agent initialization
uv run python -c "from src.agent import rag_agent; print(f'✓ Agent initialized: {rag_agent.model}')"
```

### Level 4: End-to-End CLI
```bash
# Run full CLI
uv run python -m src.cli

# In CLI, test queries:
# > hi
# > what is in the knowledge base?
# > info
# > clear
# > exit
```

### Level 5: Search Accuracy
```bash
# Verify search returns relevant results
uv run python -c "
import asyncio
from src.dependencies import AgentDependencies
from src.tools import hybrid_search

class MockContext:
    def __init__(self, deps):
        self.deps = deps

async def test():
    deps = AgentDependencies()
    await deps.initialize()
    ctx = MockContext(deps)

    # Test with known query from ingested docs
    results = await hybrid_search(ctx, 'MongoDB vector search', match_count=5)

    print(f'Hybrid search results: {len(results)}')
    for i, r in enumerate(results, 1):
        print(f'{i}. {r.document_title} - {r.similarity:.3f}')

    assert len(results) > 0, 'Expected results for MongoDB query'
    assert results[0].similarity > 0.5, 'Expected high relevance'

    print('✓ Search accuracy validated')
    await deps.cleanup()

asyncio.run(test())
"
```

---

## ACCEPTANCE CRITERIA

- [ ] `src/tools.py` created with SearchResult model
- [ ] `semantic_search()` returns list[SearchResult] from MongoDB $vectorSearch
- [ ] `hybrid_search()` returns list[SearchResult] from MongoDB $rankFusion
- [ ] Embeddings used as Python lists (NOT strings)
- [ ] $lookup joins include document title and source
- [ ] Similarity/combined scores extracted via $meta
- [ ] Error handling for missing indexes returns empty list
- [ ] `src/agent.py` created with RAGState and rag_agent
- [ ] `search_knowledge_base` tool wrapper initializes/cleans up dependencies
- [ ] Tool returns formatted string responses for LLM
- [ ] `src/cli.py` created with Rich console
- [ ] Streaming responses work in real-time
- [ ] Tool calls visible with query details
- [ ] Message history maintains conversation context
- [ ] Special commands (info, clear, exit) work
- [ ] `src/prompts.py` copied from examples
- [ ] All validation commands pass
- [ ] End-to-end CLI test successful
- [ ] Search accuracy validated against ingested data
- [ ] Error cases handled gracefully (missing indexes, connection failures)

---

## NOTES

### Design Decisions

**Why Combined Phase?**
- Tools are useless without agent framework to call them
- Can't test search without CLI interface
- Agent/tools/CLI are tightly coupled by design
- End-to-end validation requires complete system

**MongoDB Hybrid Search Advantage:**
- `$rankFusion` is native operator (MongoDB 8.0+)
- No manual score combination needed
- Reciprocal Rank Fusion built-in
- Simpler than PostgreSQL hybrid search

**StateDeps Pattern:**
- Enables shared state across tool calls
- RAGState currently empty but extensible
- Could add: search_history, user_preferences, session_info

### Critical Dependencies

1. **MongoDB Indexes**: MUST exist before testing (vector_index + text_index)
2. **Python List Embeddings**: NEVER convert to string format
3. **ObjectId Conversion**: Always `str(object_id)` for SearchResult
4. **Proper Cleanup**: Always cleanup AgentDependencies in finally block

### Performance

- Semantic search: ~200-500ms (depends on numCandidates)
- Hybrid search: ~300-700ms (combines two pipelines)
- Streaming latency: ~100-200ms time-to-first-token
- Total query-to-answer: ~1-2 seconds

### Troubleshooting

- "Index not found": Create vector_index and text_index in Atlas UI
- "No results": Check if ingestion populated chunks collection
- "Embedding dimension mismatch": Verify text-embedding-3-small (1536 dims)
- "Tool not called": Check MAIN_SYSTEM_PROMPT guides when to search
- "Streaming not working": Verify Pydantic AI version 0.1.0+
- "Connection error": Check MongoDB URI and network access in Atlas
