# Monorepo Setup Implementation Plan (Issue #2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Initialize the monorepo with FastAPI backend (all reference code reorganized), Next.js frontend with shadcn/ui, widget scaffold, Docker Compose, and Makefile.

**Architecture:** Monorepo with `apps/api` (Python/FastAPI/uv), `apps/web` (Next.js/pnpm), `packages/widget` (esbuild). Reference app code from `MongoDB-RAG-Agent-main/src/` is copied into `apps/api/src/` reorganized into a layered structure (`core/`, `models/`, `services/`, `routers/`). No local MongoDB — always connect to Atlas.

**Tech Stack:** Python 3.10+, FastAPI, uv, Next.js 14+, TypeScript, Tailwind CSS, shadcn/ui, pnpm, esbuild, Docker

---

## File Map

### New files to create

**`apps/api/`:**
- `src/__init__.py` — Package init
- `src/main.py` — FastAPI app factory, CORS, lifespan
- `src/core/__init__.py` — Core package init
- `src/core/settings.py` — Pydantic Settings (adapted from reference `src/settings.py`)
- `src/core/dependencies.py` — AgentDependencies (adapted from reference `src/dependencies.py`)
- `src/core/providers.py` — LLM/embedding providers (adapted from reference `src/providers.py`)
- `src/core/prompts.py` — System prompts (adapted from reference `src/prompts.py`)
- `src/models/__init__.py` — Models package init
- `src/models/search.py` — SearchResult Pydantic model (extracted from reference `src/tools.py`)
- `src/services/__init__.py` — Services package init
- `src/services/agent.py` — Pydantic AI agent (adapted from reference `src/agent.py`)
- `src/services/search.py` — Search functions (adapted from reference `src/tools.py`)
- `src/services/ingestion/__init__.py` — Ingestion package init
- `src/services/ingestion/ingest.py` — Pipeline (adapted from reference `src/ingestion/ingest.py`)
- `src/services/ingestion/chunker.py` — Docling wrapper (adapted from reference `src/ingestion/chunker.py`)
- `src/services/ingestion/embedder.py` — Batch embedder (adapted from reference `src/ingestion/embedder.py`)
- `src/routers/__init__.py` — Routers package init
- `src/routers/health.py` — Health check endpoint
- `src/cli.py` — CLI agent (adapted from reference `src/cli.py`)
- `tests/__init__.py` — Tests package init
- `tests/test_health.py` — Health endpoint test
- `pyproject.toml` — Python project config
- `.env.example` — Backend env template
- `Dockerfile` — API container

**`apps/web/`:**
- Created by `create-next-app` + shadcn/ui init
- `.env.example` — Frontend env template
- `Dockerfile` — Web container

**`packages/widget/`:**
- `src/index.ts` — Widget entry point placeholder
- `package.json` — Package config with esbuild
- `tsconfig.json` — TypeScript config

**Root:**
- `docker-compose.yml` — web + api services
- `Makefile` — Dev scripts
- `.env.example` — Pointer to app-level env files
- `.gitignore` — Extended for Python + Node + IDE
- `README.md` — Setup instructions

---

## Task 1: Create branch and root .gitignore

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: Create feature branch**

```bash
git checkout -b feature/monorepo-setup
```

- [ ] **Step 2: Create `.gitignore`**

Create `.gitignore` at project root:

```gitignore
# Environment
.env
.env.local
.env.*.local

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
dist/
*.egg-info/
*.egg
.venv/
venv/

# Testing
.pytest_cache/
.coverage
htmlcov/

# Node
node_modules/
.next/
out/

# Widget
packages/widget/dist/

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store

# UV
uv.lock

# Logs
*.log

# OS
Thumbs.db

# Reference app (not part of monorepo)
MongoDB-RAG-Agent-main/
```

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: add monorepo .gitignore

Covers Python, Node, IDE artifacts, and excludes reference app directory."
```

---

## Task 2: FastAPI core modules (`apps/api/src/core/`)

**Files:**
- Create: `apps/api/src/__init__.py`
- Create: `apps/api/src/core/__init__.py`
- Create: `apps/api/src/core/settings.py`
- Create: `apps/api/src/core/dependencies.py`
- Create: `apps/api/src/core/providers.py`
- Create: `apps/api/src/core/prompts.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p apps/api/src/core
```

- [ ] **Step 2: Create `apps/api/src/__init__.py`**

```python
"""MongoRAG API — Multi-tenant RAG backend."""
```

- [ ] **Step 3: Create `apps/api/src/core/__init__.py`**

```python
"""Core configuration and dependencies."""
```

- [ ] **Step 4: Create `apps/api/src/core/settings.py`**

Copy from `MongoDB-RAG-Agent-main/src/settings.py` with no changes (imports are self-contained):

```python
"""Settings configuration for MongoDB RAG Agent."""

from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict
from dotenv import load_dotenv
from typing import Optional

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = ConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # MongoDB Configuration
    mongodb_uri: str = Field(..., description="MongoDB Atlas connection string")

    mongodb_database: str = Field(default="rag_db", description="MongoDB database name")

    mongodb_collection_documents: str = Field(
        default="documents", description="Collection for source documents"
    )

    mongodb_collection_chunks: str = Field(
        default="chunks", description="Collection for document chunks with embeddings"
    )

    mongodb_vector_index: str = Field(
        default="vector_index",
        description="Vector search index name (must be created in Atlas UI)",
    )

    mongodb_text_index: str = Field(
        default="text_index",
        description="Full-text search index name (must be created in Atlas UI)",
    )

    # LLM Configuration (OpenAI-compatible)
    llm_provider: str = Field(
        default="openrouter",
        description="LLM provider (openai, anthropic, gemini, ollama, etc.)",
    )

    llm_api_key: str = Field(..., description="API key for the LLM provider")

    llm_model: str = Field(
        default="anthropic/claude-haiku-4.5",
        description="Model to use for search and summarization",
    )

    llm_base_url: Optional[str] = Field(
        default="https://openrouter.ai/api/v1",
        description="Base URL for the LLM API (for OpenAI-compatible providers)",
    )

    # Embedding Configuration
    embedding_provider: str = Field(default="openai", description="Embedding provider")

    embedding_api_key: str = Field(..., description="API key for embedding provider")

    embedding_model: str = Field(
        default="text-embedding-3-small", description="Embedding model to use"
    )

    embedding_base_url: Optional[str] = Field(
        default="https://api.openai.com/v1", description="Base URL for embedding API"
    )

    embedding_dimension: int = Field(
        default=1536,
        description="Embedding vector dimension (1536 for text-embedding-3-small)",
    )

    # Search Configuration
    default_match_count: int = Field(
        default=10, description="Default number of search results to return"
    )

    max_match_count: int = Field(
        default=50, description="Maximum number of search results allowed"
    )

    default_text_weight: float = Field(
        default=0.3, description="Default text weight for hybrid search (0-1)"
    )


def load_settings() -> Settings:
    """Load settings with proper error handling."""
    try:
        return Settings()
    except Exception as e:
        error_msg = f"Failed to load settings: {e}"
        if "mongodb_uri" in str(e).lower():
            error_msg += "\nMake sure to set MONGODB_URI in your .env file"
        if "llm_api_key" in str(e).lower():
            error_msg += "\nMake sure to set LLM_API_KEY in your .env file"
        if "embedding_api_key" in str(e).lower():
            error_msg += "\nMake sure to set EMBEDDING_API_KEY in your .env file"
        raise ValueError(error_msg) from e
```

- [ ] **Step 5: Create `apps/api/src/core/dependencies.py`**

Copy from `MongoDB-RAG-Agent-main/src/dependencies.py` — update the import path:

```python
"""Dependencies for MongoDB RAG Agent."""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import logging
from pymongo import AsyncMongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import openai
from src.core.settings import load_settings

logger = logging.getLogger(__name__)


@dataclass
class AgentDependencies:
    """Dependencies injected into the agent context."""

    # Core dependencies
    mongo_client: Optional[AsyncMongoClient] = None
    db: Optional[Any] = None
    openai_client: Optional[openai.AsyncOpenAI] = None
    settings: Optional[Any] = None

    # Session context
    session_id: Optional[str] = None
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    query_history: list = field(default_factory=list)

    async def initialize(self) -> None:
        """
        Initialize external connections.

        Raises:
            ConnectionFailure: If MongoDB connection fails
            ServerSelectionTimeoutError: If MongoDB server selection times out
            ValueError: If settings cannot be loaded
        """
        if not self.settings:
            self.settings = load_settings()
            logger.info("settings_loaded", database=self.settings.mongodb_database)

        # Initialize MongoDB client
        if not self.mongo_client:
            try:
                self.mongo_client = AsyncMongoClient(
                    self.settings.mongodb_uri, serverSelectionTimeoutMS=5000
                )
                self.db = self.mongo_client[self.settings.mongodb_database]

                # Verify connection with ping
                await self.mongo_client.admin.command("ping")
                logger.info(
                    "mongodb_connected",
                    database=self.settings.mongodb_database,
                    collections={
                        "documents": self.settings.mongodb_collection_documents,
                        "chunks": self.settings.mongodb_collection_chunks,
                    },
                )
            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                logger.exception("mongodb_connection_failed", error=str(e))
                raise

        # Initialize OpenAI client for embeddings
        if not self.openai_client:
            self.openai_client = openai.AsyncOpenAI(
                api_key=self.settings.embedding_api_key,
                base_url=self.settings.embedding_base_url,
            )
            logger.info(
                "openai_client_initialized",
                model=self.settings.embedding_model,
                dimension=self.settings.embedding_dimension,
            )

    async def cleanup(self) -> None:
        """Clean up external connections."""
        if self.mongo_client:
            await self.mongo_client.close()
            self.mongo_client = None
            self.db = None
            logger.info("mongodb_connection_closed")

    async def get_embedding(self, text: str) -> list[float]:
        """
        Generate embedding for text using OpenAI.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats

        Raises:
            Exception: If embedding generation fails
        """
        if not self.openai_client:
            await self.initialize()

        response = await self.openai_client.embeddings.create(
            model=self.settings.embedding_model, input=text
        )
        # Return as list of floats - MongoDB stores as native array
        return response.data[0].embedding

    def set_user_preference(self, key: str, value: Any) -> None:
        """
        Set a user preference for the session.

        Args:
            key: Preference key
            value: Preference value
        """
        self.user_preferences[key] = value

    def add_to_history(self, query: str) -> None:
        """
        Add a query to the search history.

        Args:
            query: Search query to add to history
        """
        self.query_history.append(query)
        # Keep only last 10 queries
        if len(self.query_history) > 10:
            self.query_history.pop(0)
```

- [ ] **Step 6: Create `apps/api/src/core/providers.py`**

Copy from `MongoDB-RAG-Agent-main/src/providers.py` — update import:

```python
"""Model providers for Semantic Search Agent."""

from typing import Optional
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.openai import OpenAIModel
from src.core.settings import load_settings


def get_llm_model(model_choice: Optional[str] = None) -> OpenAIModel:
    """
    Get LLM model configuration based on environment variables.
    Supports any OpenAI-compatible API provider.

    Args:
        model_choice: Optional override for model choice

    Returns:
        Configured OpenAI-compatible model
    """
    settings = load_settings()

    llm_choice = model_choice or settings.llm_model
    base_url = settings.llm_base_url
    api_key = settings.llm_api_key

    # Create provider based on configuration
    provider = OpenAIProvider(base_url=base_url, api_key=api_key)

    return OpenAIModel(llm_choice, provider=provider)


def get_embedding_model() -> OpenAIModel:
    """
    Get embedding model configuration.
    Uses OpenAI embeddings API (or compatible provider).

    Returns:
        Configured embedding model
    """
    settings = load_settings()

    # For embeddings, use the same provider configuration
    provider = OpenAIProvider(
        base_url=settings.llm_base_url, api_key=settings.llm_api_key
    )

    return OpenAIModel(settings.embedding_model, provider=provider)


def get_model_info() -> dict:
    """
    Get information about current model configuration.

    Returns:
        Dictionary with model configuration info
    """
    settings = load_settings()

    return {
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "llm_base_url": settings.llm_base_url,
        "embedding_model": settings.embedding_model,
    }


def validate_llm_configuration() -> bool:
    """
    Validate that LLM configuration is properly set.

    Returns:
        True if configuration is valid
    """
    try:
        # Check if we can create a model instance
        get_llm_model()
        return True
    except Exception as e:
        print(f"LLM configuration validation failed: {e}")
        return False
```

- [ ] **Step 7: Create `apps/api/src/core/prompts.py`**

Copy from `MongoDB-RAG-Agent-main/src/prompts.py` — no import changes needed:

```python
"""System prompts for MongoDB RAG Agent."""

MAIN_SYSTEM_PROMPT = """You are a helpful assistant with access to a knowledge base that you can search when needed.

ALWAYS Start with Hybrid search

## Your Capabilities:
1. **Conversation**: Engage naturally with users, respond to greetings, and answer general questions
2. **Semantic Search**: When users ask for information from the knowledge base, use hybrid_search for conceptual queries
3. **Hybrid Search**: For specific facts or technical queries, use hybrid_search
4. **Information Synthesis**: Transform search results into coherent responses

## When to Search:
- ONLY search when users explicitly ask for information that would be in the knowledge base
- For greetings (hi, hello, hey) → Just respond conversationally, no search needed
- For general questions about yourself → Answer directly, no search needed
- For requests about specific topics or information → Use the appropriate search tool

## Search Strategy (when searching):
- Conceptual/thematic queries → Use hybrid_search
- Specific facts/technical terms → Use hybrid_search with appropriate text_weight
- Start with lower match_count (5-10) for focused results

## Response Guidelines:
- Be conversational and natural
- Only cite sources when you've actually performed a search
- If no search is needed, just respond directly
- Be helpful and friendly

Remember: Not every interaction requires a search. Use your judgment about when to search the knowledge base."""
```

- [ ] **Step 8: Commit**

```bash
git add apps/api/src/__init__.py apps/api/src/core/
git commit -m "feat(api): add core modules (settings, dependencies, providers, prompts)

Adapted from MongoDB-RAG-Agent-main/src/ with import paths updated
for layered structure."
```

---

## Task 3: FastAPI models (`apps/api/src/models/`)

**Files:**
- Create: `apps/api/src/models/__init__.py`
- Create: `apps/api/src/models/search.py`

- [ ] **Step 1: Create directory**

```bash
mkdir -p apps/api/src/models
```

- [ ] **Step 2: Create `apps/api/src/models/__init__.py`**

```python
"""Pydantic models for request/response/domain objects."""
```

- [ ] **Step 3: Create `apps/api/src/models/search.py`**

Extract `SearchResult` from reference `src/tools.py`:

```python
"""Search result models."""

from typing import Dict, Any
from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """Model for search results."""

    chunk_id: str = Field(..., description="MongoDB ObjectId of chunk as string")
    document_id: str = Field(..., description="Parent document ObjectId as string")
    content: str = Field(..., description="Chunk text content")
    similarity: float = Field(..., description="Relevance score (0-1)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Chunk metadata")
    document_title: str = Field(..., description="Title from document lookup")
    document_source: str = Field(..., description="Source from document lookup")
```

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/models/
git commit -m "feat(api): add search result model

Extracted SearchResult from tools.py into models layer."
```

---

## Task 4: FastAPI services — search (`apps/api/src/services/search.py`)

**Files:**
- Create: `apps/api/src/services/__init__.py`
- Create: `apps/api/src/services/search.py`

- [ ] **Step 1: Create directory**

```bash
mkdir -p apps/api/src/services
```

- [ ] **Step 2: Create `apps/api/src/services/__init__.py`**

```python
"""Business logic services."""
```

- [ ] **Step 3: Create `apps/api/src/services/search.py`**

Adapted from reference `src/tools.py` — `SearchResult` import changed, `AgentDependencies` import changed:

```python
"""Search tools for MongoDB RAG Agent."""

import asyncio
import logging
from typing import Optional, List, Dict

from pydantic_ai import RunContext
from pymongo.errors import OperationFailure

from src.core.dependencies import AgentDependencies
from src.models.search import SearchResult

logger = logging.getLogger(__name__)


async def semantic_search(
    ctx: RunContext[AgentDependencies],
    query: str,
    match_count: Optional[int] = None
) -> List[SearchResult]:
    """
    Perform pure semantic search using MongoDB vector similarity.

    Args:
        ctx: Agent runtime context with dependencies
        query: Search query text
        match_count: Number of results to return (default: 10)

    Returns:
        List of search results ordered by similarity

    Raises:
        OperationFailure: If MongoDB operation fails (e.g., missing index)
    """
    try:
        deps = ctx.deps

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
                    "numCandidates": 100,
                    "limit": match_count
                }
            },
            {
                "$lookup": {
                    "from": deps.settings.mongodb_collection_documents,
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

        # Execute aggregation
        collection = deps.db[deps.settings.mongodb_collection_chunks]
        cursor = await collection.aggregate(pipeline)
        results = [doc async for doc in cursor][:match_count]

        # Convert to SearchResult objects (ObjectId -> str conversion)
        search_results = [
            SearchResult(
                chunk_id=str(doc['chunk_id']),
                document_id=str(doc['document_id']),
                content=doc['content'],
                similarity=doc['similarity'],
                metadata=doc.get('metadata', {}),
                document_title=doc['document_title'],
                document_source=doc['document_source']
            )
            for doc in results
        ]

        logger.info(
            f"semantic_search_completed: query={query}, results={len(search_results)}, match_count={match_count}"
        )

        return search_results

    except OperationFailure as e:
        error_code = e.code if hasattr(e, 'code') else None
        logger.error(
            f"semantic_search_failed: query={query}, error={str(e)}, code={error_code}"
        )
        return []
    except Exception as e:
        logger.exception(f"semantic_search_error: query={query}, error={str(e)}")
        return []


async def text_search(
    ctx: RunContext[AgentDependencies],
    query: str,
    match_count: Optional[int] = None
) -> List[SearchResult]:
    """
    Perform full-text search using MongoDB Atlas Search.

    Args:
        ctx: Agent runtime context with dependencies
        query: Search query text
        match_count: Number of results to return (default: 10)

    Returns:
        List of search results ordered by text relevance

    Raises:
        OperationFailure: If MongoDB operation fails (e.g., missing index)
    """
    try:
        deps = ctx.deps

        if match_count is None:
            match_count = deps.settings.default_match_count

        match_count = min(match_count, deps.settings.max_match_count)

        pipeline = [
            {
                "$search": {
                    "index": deps.settings.mongodb_text_index,
                    "text": {
                        "query": query,
                        "path": "content",
                        "fuzzy": {
                            "maxEdits": 2,
                            "prefixLength": 3
                        }
                    }
                }
            },
            {
                "$limit": match_count * 2
            },
            {
                "$lookup": {
                    "from": deps.settings.mongodb_collection_documents,
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
                    "similarity": {"$meta": "searchScore"},
                    "metadata": 1,
                    "document_title": "$document_info.title",
                    "document_source": "$document_info.source"
                }
            }
        ]

        collection = deps.db[deps.settings.mongodb_collection_chunks]
        cursor = await collection.aggregate(pipeline)
        results = [doc async for doc in cursor][:match_count * 2]

        search_results = [
            SearchResult(
                chunk_id=str(doc['chunk_id']),
                document_id=str(doc['document_id']),
                content=doc['content'],
                similarity=doc['similarity'],
                metadata=doc.get('metadata', {}),
                document_title=doc['document_title'],
                document_source=doc['document_source']
            )
            for doc in results
        ]

        logger.info(
            f"text_search_completed: query={query}, results={len(search_results)}, match_count={match_count}"
        )

        return search_results

    except OperationFailure as e:
        error_code = e.code if hasattr(e, 'code') else None
        logger.error(
            f"text_search_failed: query={query}, error={str(e)}, code={error_code}"
        )
        return []
    except Exception as e:
        logger.exception(f"text_search_error: query={query}, error={str(e)}")
        return []


def reciprocal_rank_fusion(
    search_results_list: List[List[SearchResult]],
    k: int = 60
) -> List[SearchResult]:
    """
    Merge multiple ranked lists using Reciprocal Rank Fusion.

    Args:
        search_results_list: List of ranked result lists from different searches
        k: RRF constant (default: 60, standard in literature)

    Returns:
        Unified list of results sorted by combined RRF score
    """
    rrf_scores: Dict[str, float] = {}
    chunk_map: Dict[str, SearchResult] = {}

    for results in search_results_list:
        for rank, result in enumerate(results):
            chunk_id = result.chunk_id

            rrf_score = 1.0 / (k + rank)

            if chunk_id in rrf_scores:
                rrf_scores[chunk_id] += rrf_score
            else:
                rrf_scores[chunk_id] = rrf_score
                chunk_map[chunk_id] = result

    sorted_chunks = sorted(
        rrf_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    merged_results = []
    for chunk_id, rrf_score in sorted_chunks:
        result = chunk_map[chunk_id]
        merged_result = SearchResult(
            chunk_id=result.chunk_id,
            document_id=result.document_id,
            content=result.content,
            similarity=rrf_score,
            metadata=result.metadata,
            document_title=result.document_title,
            document_source=result.document_source
        )
        merged_results.append(merged_result)

    logger.info(f"RRF merged {len(search_results_list)} result lists into {len(merged_results)} unique results")

    return merged_results


async def hybrid_search(
    ctx: RunContext[AgentDependencies],
    query: str,
    match_count: Optional[int] = None,
    text_weight: Optional[float] = None
) -> List[SearchResult]:
    """
    Perform hybrid search combining semantic and keyword matching.

    Args:
        ctx: Agent runtime context with dependencies
        query: Search query text
        match_count: Number of results to return (default: 10)
        text_weight: Weight for text matching (0-1, not used with RRF)

    Returns:
        List of search results sorted by combined RRF score
    """
    try:
        deps = ctx.deps

        if match_count is None:
            match_count = deps.settings.default_match_count

        match_count = min(match_count, deps.settings.max_match_count)

        fetch_count = match_count * 2

        logger.info(f"hybrid_search starting: query='{query}', match_count={match_count}")

        semantic_results, text_results = await asyncio.gather(
            semantic_search(ctx, query, fetch_count),
            text_search(ctx, query, fetch_count),
            return_exceptions=True
        )

        if isinstance(semantic_results, Exception):
            logger.warning(f"Semantic search failed: {semantic_results}, using text results only")
            semantic_results = []
        if isinstance(text_results, Exception):
            logger.warning(f"Text search failed: {text_results}, using semantic results only")
            text_results = []

        if not semantic_results and not text_results:
            logger.error("Both semantic and text search failed")
            return []

        merged_results = reciprocal_rank_fusion(
            [semantic_results, text_results],
            k=60
        )

        final_results = merged_results[:match_count]

        logger.info(
            f"hybrid_search_completed: query='{query}', "
            f"semantic={len(semantic_results)}, text={len(text_results)}, "
            f"merged={len(merged_results)}, returned={len(final_results)}"
        )

        return final_results

    except Exception as e:
        logger.exception(f"hybrid_search_error: query={query}, error={str(e)}")
        try:
            logger.info("Falling back to semantic search only")
            return await semantic_search(ctx, query, match_count)
        except:
            return []
```

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/services/__init__.py apps/api/src/services/search.py
git commit -m "feat(api): add search services (semantic, text, hybrid, RRF)

Adapted from MongoDB-RAG-Agent-main/src/tools.py with imports updated
for layered structure. SearchResult model extracted to models layer."
```

---

## Task 5: FastAPI services — agent (`apps/api/src/services/agent.py`)

**Files:**
- Create: `apps/api/src/services/agent.py`

- [ ] **Step 1: Create `apps/api/src/services/agent.py`**

Adapted from reference `src/agent.py` — all imports updated:

```python
"""Main MongoDB RAG agent implementation with shared state."""

from pydantic_ai import Agent, RunContext
from pydantic import BaseModel
from typing import Optional

from pydantic_ai.ag_ui import StateDeps

from src.core.providers import get_llm_model
from src.core.dependencies import AgentDependencies
from src.core.prompts import MAIN_SYSTEM_PROMPT
from src.services.search import semantic_search, hybrid_search, text_search


class RAGState(BaseModel):
    """Minimal shared state for the RAG agent."""
    pass


# Create the RAG agent with AGUI support
rag_agent = Agent(
    get_llm_model(),
    deps_type=StateDeps[RAGState],
    system_prompt=MAIN_SYSTEM_PROMPT
)


@rag_agent.tool
async def search_knowledge_base(
    ctx: RunContext[StateDeps[RAGState]],
    query: str,
    match_count: Optional[int] = 5,
    search_type: Optional[str] = "hybrid"
) -> str:
    """
    Search the knowledge base for relevant information.

    Args:
        ctx: Agent runtime context with state dependencies
        query: Search query text
        match_count: Number of results to return (default: 5)
        search_type: Type of search - "semantic" or "text" or "hybrid" (default: hybrid)

    Returns:
        String containing the retrieved information formatted for the LLM
    """
    try:
        # Initialize database connection
        agent_deps = AgentDependencies()
        await agent_deps.initialize()

        # Create a context wrapper for the search tools
        class DepsWrapper:
            def __init__(self, deps):
                self.deps = deps

        deps_ctx = DepsWrapper(agent_deps)

        # Perform the search based on type
        if search_type == "hybrid":
            results = await hybrid_search(
                ctx=deps_ctx,
                query=query,
                match_count=match_count
            )
        elif search_type == "semantic":
            results = await semantic_search(
                ctx=deps_ctx,
                query=query,
                match_count=match_count
            )
        else:
            results = await text_search(
                ctx=deps_ctx,
                query=query,
                match_count=match_count
            )

        # Clean up
        await agent_deps.cleanup()

        # Format results as a simple string
        if not results:
            return "No relevant information found in the knowledge base."

        # Build a formatted response
        response_parts = [f"Found {len(results)} relevant documents:\n"]

        for i, result in enumerate(results, 1):
            response_parts.append(f"\n--- Document {i}: {result.document_title} (relevance: {result.similarity:.2f}) ---")
            response_parts.append(result.content)

        return "\n".join(response_parts)

    except Exception as e:
        return f"Error searching knowledge base: {str(e)}"
```

- [ ] **Step 2: Commit**

```bash
git add apps/api/src/services/agent.py
git commit -m "feat(api): add Pydantic AI RAG agent service

Adapted from MongoDB-RAG-Agent-main/src/agent.py with imports updated
for layered structure."
```

---

## Task 6: FastAPI services — ingestion (`apps/api/src/services/ingestion/`)

**Files:**
- Create: `apps/api/src/services/ingestion/__init__.py`
- Create: `apps/api/src/services/ingestion/chunker.py`
- Create: `apps/api/src/services/ingestion/embedder.py`
- Create: `apps/api/src/services/ingestion/ingest.py`

- [ ] **Step 1: Create directory**

```bash
mkdir -p apps/api/src/services/ingestion
```

- [ ] **Step 2: Create `apps/api/src/services/ingestion/__init__.py`**

```python
"""Document ingestion pipeline for MongoDB RAG Agent."""
```

- [ ] **Step 3: Create `apps/api/src/services/ingestion/chunker.py`**

Copy from `MongoDB-RAG-Agent-main/src/ingestion/chunker.py` — no import changes needed (self-contained):

```python
"""
Docling HybridChunker implementation for intelligent document splitting.

This module uses Docling's built-in HybridChunker which combines:
- Token-aware chunking (uses actual tokenizer)
- Document structure preservation (headings, sections, tables)
- Semantic boundary respect (paragraphs, code blocks)
- Contextualized output (chunks include heading hierarchy)

Benefits over custom chunking:
- Fast (no LLM API calls)
- Token-precise (not character-based estimates)
- Better for RAG (chunks include document context)
- Battle-tested (maintained by Docling team)
"""

import os
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from dotenv import load_dotenv
from transformers import AutoTokenizer
from docling.chunking import HybridChunker
from docling_core.types.doc import DoclingDocument

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class ChunkingConfig:
    """Configuration for DoclingHybridChunker."""
    chunk_size: int = 1000
    chunk_overlap: int = 200
    max_chunk_size: int = 2000
    min_chunk_size: int = 100
    max_tokens: int = 512

    def __post_init__(self):
        """Validate configuration."""
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("Chunk overlap must be less than chunk size")
        if self.min_chunk_size <= 0:
            raise ValueError("Minimum chunk size must be positive")


@dataclass
class DocumentChunk:
    """Represents a document chunk with optional embedding."""
    content: str
    index: int
    start_char: int
    end_char: int
    metadata: Dict[str, Any]
    token_count: Optional[int] = None
    embedding: Optional[List[float]] = None

    def __post_init__(self):
        """Calculate token count if not provided."""
        if self.token_count is None:
            self.token_count = len(self.content) // 4


class DoclingHybridChunker:
    """
    Docling HybridChunker wrapper for intelligent document splitting.

    This chunker uses Docling's built-in HybridChunker which:
    - Respects document structure (sections, paragraphs, tables)
    - Is token-aware (fits embedding model limits)
    - Preserves semantic coherence
    - Includes heading context in chunks
    """

    def __init__(self, config: ChunkingConfig):
        """
        Initialize chunker.

        Args:
            config: Chunking configuration
        """
        self.config = config

        model_id = "sentence-transformers/all-MiniLM-L6-v2"
        logger.info(f"Initializing tokenizer: {model_id}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)

        self.chunker = HybridChunker(
            tokenizer=self.tokenizer,
            max_tokens=config.max_tokens,
            merge_peers=True
        )

        logger.info(f"HybridChunker initialized (max_tokens={config.max_tokens})")

    async def chunk_document(
        self,
        content: str,
        title: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None,
        docling_doc: Optional[DoclingDocument] = None
    ) -> List[DocumentChunk]:
        """
        Chunk a document using Docling's HybridChunker.

        Args:
            content: Document content (markdown format)
            title: Document title
            source: Document source
            metadata: Additional metadata
            docling_doc: Optional pre-converted DoclingDocument (for efficiency)

        Returns:
            List of document chunks with contextualized content
        """
        if not content.strip():
            return []

        base_metadata = {
            "title": title,
            "source": source,
            "chunk_method": "hybrid",
            **(metadata or {})
        }

        if docling_doc is None:
            logger.warning("No DoclingDocument provided, using simple chunking fallback")
            return self._simple_fallback_chunk(content, base_metadata)

        try:
            chunk_iter = self.chunker.chunk(dl_doc=docling_doc)
            chunks = list(chunk_iter)

            document_chunks = []
            current_pos = 0

            for i, chunk in enumerate(chunks):
                contextualized_text = self.chunker.contextualize(chunk=chunk)
                token_count = len(self.tokenizer.encode(contextualized_text))

                chunk_metadata = {
                    **base_metadata,
                    "total_chunks": len(chunks),
                    "token_count": token_count,
                    "has_context": True
                }

                start_char = current_pos
                end_char = start_char + len(contextualized_text)

                document_chunks.append(DocumentChunk(
                    content=contextualized_text.strip(),
                    index=i,
                    start_char=start_char,
                    end_char=end_char,
                    metadata=chunk_metadata,
                    token_count=token_count
                ))

                current_pos = end_char

            logger.info(f"Created {len(document_chunks)} chunks using HybridChunker")
            return document_chunks

        except Exception as e:
            logger.error(f"HybridChunker failed: {e}, falling back to simple chunking")
            return self._simple_fallback_chunk(content, base_metadata)

    def _simple_fallback_chunk(
        self,
        content: str,
        base_metadata: Dict[str, Any]
    ) -> List[DocumentChunk]:
        """
        Simple fallback chunking when HybridChunker can't be used.

        Args:
            content: Content to chunk
            base_metadata: Base metadata for chunks

        Returns:
            List of document chunks
        """
        chunks = []
        chunk_size = self.config.chunk_size
        overlap = self.config.chunk_overlap

        start = 0
        chunk_index = 0

        while start < len(content):
            end = start + chunk_size

            if end >= len(content):
                chunk_text = content[start:]
            else:
                chunk_end = end
                for i in range(end, max(start + self.config.min_chunk_size, end - 200), -1):
                    if i < len(content) and content[i] in '.!?\n':
                        chunk_end = i + 1
                        break
                chunk_text = content[start:chunk_end]
                end = chunk_end

            if chunk_text.strip():
                token_count = len(self.tokenizer.encode(chunk_text))

                chunks.append(DocumentChunk(
                    content=chunk_text.strip(),
                    index=chunk_index,
                    start_char=start,
                    end_char=end,
                    metadata={
                        **base_metadata,
                        "chunk_method": "simple_fallback",
                        "total_chunks": -1
                    },
                    token_count=token_count
                ))

                chunk_index += 1

            start = end - overlap

        for chunk in chunks:
            chunk.metadata["total_chunks"] = len(chunks)

        logger.info(f"Created {len(chunks)} chunks using simple fallback")
        return chunks


def create_chunker(config: ChunkingConfig):
    """
    Create DoclingHybridChunker for intelligent document splitting.

    Args:
        config: Chunking configuration

    Returns:
        DoclingHybridChunker instance
    """
    return DoclingHybridChunker(config)
```

- [ ] **Step 4: Create `apps/api/src/services/ingestion/embedder.py`**

Adapted from reference — update import path:

```python
"""Document embedding generation for vector search."""

import logging
from typing import List, Optional
from datetime import datetime

from dotenv import load_dotenv
import openai

from src.services.ingestion.chunker import DocumentChunk
from src.core.settings import load_settings

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Initialize client with settings
settings = load_settings()
embedding_client = openai.AsyncOpenAI(
    api_key=settings.embedding_api_key,
    base_url=settings.embedding_base_url
)
EMBEDDING_MODEL = settings.embedding_model


class EmbeddingGenerator:
    """Generates embeddings for document chunks."""

    def __init__(
        self,
        model: str = EMBEDDING_MODEL,
        batch_size: int = 100
    ):
        """
        Initialize embedding generator.

        Args:
            model: Embedding model to use
            batch_size: Number of texts to process in parallel
        """
        self.model = model
        self.batch_size = batch_size

        self.model_configs = {
            "text-embedding-3-small": {"dimensions": 1536, "max_tokens": 8191},
            "text-embedding-3-large": {"dimensions": 3072, "max_tokens": 8191},
            "text-embedding-ada-002": {"dimensions": 1536, "max_tokens": 8191}
        }

        self.config = self.model_configs.get(
            model,
            {"dimensions": 1536, "max_tokens": 8191}
        )

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        if len(text) > self.config["max_tokens"] * 4:
            text = text[:self.config["max_tokens"] * 4]

        response = await embedding_client.embeddings.create(
            model=self.model,
            input=text
        )

        return response.data[0].embedding

    async def generate_embeddings_batch(
        self,
        texts: List[str]
    ) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        processed_texts = []
        for text in texts:
            if len(text) > self.config["max_tokens"] * 4:
                text = text[:self.config["max_tokens"] * 4]
            processed_texts.append(text)

        response = await embedding_client.embeddings.create(
            model=self.model,
            input=processed_texts
        )

        return [data.embedding for data in response.data]

    async def embed_chunks(
        self,
        chunks: List[DocumentChunk],
        progress_callback: Optional[callable] = None
    ) -> List[DocumentChunk]:
        """
        Generate embeddings for document chunks.

        Args:
            chunks: List of document chunks
            progress_callback: Optional callback for progress updates

        Returns:
            Chunks with embeddings added
        """
        if not chunks:
            return chunks

        logger.info(f"Generating embeddings for {len(chunks)} chunks")

        embedded_chunks = []
        total_batches = (len(chunks) + self.batch_size - 1) // self.batch_size

        for i in range(0, len(chunks), self.batch_size):
            batch_chunks = chunks[i:i + self.batch_size]
            batch_texts = [chunk.content for chunk in batch_chunks]

            embeddings = await self.generate_embeddings_batch(batch_texts)

            for chunk, embedding in zip(batch_chunks, embeddings):
                embedded_chunk = DocumentChunk(
                    content=chunk.content,
                    index=chunk.index,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                    metadata={
                        **chunk.metadata,
                        "embedding_model": self.model,
                        "embedding_generated_at": datetime.now().isoformat()
                    },
                    token_count=chunk.token_count
                )
                embedded_chunk.embedding = embedding
                embedded_chunks.append(embedded_chunk)

            current_batch = (i // self.batch_size) + 1
            if progress_callback:
                progress_callback(current_batch, total_batches)

            logger.info(f"Processed batch {current_batch}/{total_batches}")

        logger.info(f"Generated embeddings for {len(embedded_chunks)} chunks")
        return embedded_chunks

    async def embed_query(self, query: str) -> List[float]:
        """
        Generate embedding for a search query.

        Args:
            query: Search query

        Returns:
            Query embedding
        """
        return await self.generate_embedding(query)

    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings for this model."""
        return self.config["dimensions"]


def create_embedder(model: str = EMBEDDING_MODEL, **kwargs) -> EmbeddingGenerator:
    """
    Create embedding generator.

    Args:
        model: Embedding model to use
        **kwargs: Additional arguments for EmbeddingGenerator

    Returns:
        EmbeddingGenerator instance
    """
    return EmbeddingGenerator(model=model, **kwargs)
```

- [ ] **Step 5: Create `apps/api/src/services/ingestion/ingest.py`**

Adapted from reference — update import paths:

```python
"""
Main ingestion script for processing documents into MongoDB vector database.

This adapts the examples/ingestion/ingest.py pipeline to use MongoDB instead of PostgreSQL,
changing only the database layer while preserving all document processing logic.
"""

import os
import asyncio
import logging
import glob
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import argparse
from dataclasses import dataclass

from pymongo import AsyncMongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from bson import ObjectId
from dotenv import load_dotenv

from src.services.ingestion.chunker import ChunkingConfig, create_chunker, DocumentChunk
from src.services.ingestion.embedder import create_embedder
from src.core.settings import load_settings

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class IngestionConfig:
    """Configuration for document ingestion."""
    chunk_size: int = 1000
    chunk_overlap: int = 200
    max_chunk_size: int = 2000
    max_tokens: int = 512


@dataclass
class IngestionResult:
    """Result of document ingestion."""
    document_id: str
    title: str
    chunks_created: int
    processing_time_ms: float
    errors: List[str]


class DocumentIngestionPipeline:
    """Pipeline for ingesting documents into MongoDB vector database."""

    def __init__(
        self,
        config: IngestionConfig,
        documents_folder: str = "documents",
        clean_before_ingest: bool = True
    ):
        """
        Initialize ingestion pipeline.

        Args:
            config: Ingestion configuration
            documents_folder: Folder containing documents
            clean_before_ingest: Whether to clean existing data before ingestion
        """
        self.config = config
        self.documents_folder = documents_folder
        self.clean_before_ingest = clean_before_ingest

        self.settings = load_settings()

        self.mongo_client: Optional[AsyncMongoClient] = None
        self.db: Optional[Any] = None

        self.chunker_config = ChunkingConfig(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            max_chunk_size=config.max_chunk_size,
            max_tokens=config.max_tokens
        )

        self.chunker = create_chunker(self.chunker_config)
        self.embedder = create_embedder()

        self._initialized = False

    async def initialize(self) -> None:
        """
        Initialize MongoDB connections.

        Raises:
            ConnectionFailure: If MongoDB connection fails
            ServerSelectionTimeoutError: If MongoDB server selection times out
        """
        if self._initialized:
            return

        logger.info("Initializing ingestion pipeline...")

        try:
            self.mongo_client = AsyncMongoClient(
                self.settings.mongodb_uri,
                serverSelectionTimeoutMS=5000
            )
            self.db = self.mongo_client[self.settings.mongodb_database]

            await self.mongo_client.admin.command("ping")
            logger.info(
                f"Connected to MongoDB database: {self.settings.mongodb_database}"
            )

        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.exception("mongodb_connection_failed", error=str(e))
            raise

        self._initialized = True
        logger.info("Ingestion pipeline initialized")

    async def close(self) -> None:
        """Close MongoDB connections."""
        if self._initialized and self.mongo_client:
            await self.mongo_client.close()
            self.mongo_client = None
            self.db = None
            self._initialized = False
            logger.info("MongoDB connection closed")

    def _find_document_files(self) -> List[str]:
        """
        Find all supported document files in the documents folder.

        Returns:
            List of file paths
        """
        if not os.path.exists(self.documents_folder):
            logger.error(f"Documents folder not found: {self.documents_folder}")
            return []

        patterns = [
            "*.md", "*.markdown", "*.txt",
            "*.pdf",
            "*.docx", "*.doc",
            "*.pptx", "*.ppt",
            "*.xlsx", "*.xls",
            "*.html", "*.htm",
            "*.mp3", "*.wav", "*.m4a", "*.flac",
        ]
        files = []

        for pattern in patterns:
            files.extend(
                glob.glob(
                    os.path.join(self.documents_folder, "**", pattern),
                    recursive=True
                )
            )

        return sorted(files)

    def _read_document(self, file_path: str) -> tuple[str, Optional[Any]]:
        """
        Read document content from file - supports multiple formats via Docling.

        Args:
            file_path: Path to the document file

        Returns:
            Tuple of (markdown_content, docling_document).
            docling_document is None only for text files.
        """
        file_ext = os.path.splitext(file_path)[1].lower()

        audio_formats = ['.mp3', '.wav', '.m4a', '.flac']
        if file_ext in audio_formats:
            return self._transcribe_audio(file_path)

        docling_formats = [
            '.pdf', '.docx', '.doc', '.pptx', '.ppt',
            '.xlsx', '.xls', '.html', '.htm',
            '.md', '.markdown'
        ]

        if file_ext in docling_formats:
            try:
                from docling.document_converter import DocumentConverter

                logger.info(
                    f"Converting {file_ext} file using Docling: "
                    f"{os.path.basename(file_path)}"
                )

                converter = DocumentConverter()
                result = converter.convert(file_path)

                markdown_content = result.document.export_to_markdown()
                logger.info(
                    f"Successfully converted {os.path.basename(file_path)} "
                    f"to markdown"
                )

                return (markdown_content, result.document)

            except Exception as e:
                logger.error(f"Failed to convert {file_path} with Docling: {e}")
                logger.warning(f"Falling back to raw text extraction for {file_path}")
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        return (f.read(), None)
                except Exception:
                    return (
                        f"[Error: Could not read file {os.path.basename(file_path)}]",
                        None
                    )

        else:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return (f.read(), None)
            except UnicodeDecodeError:
                with open(file_path, 'r', encoding='latin-1') as f:
                    return (f.read(), None)

    def _transcribe_audio(self, file_path: str) -> tuple[str, Optional[Any]]:
        """
        Transcribe audio file using Whisper ASR via Docling.

        Args:
            file_path: Path to the audio file

        Returns:
            Tuple of (markdown_content, docling_document)
        """
        try:
            from pathlib import Path
            from docling.document_converter import (
                DocumentConverter,
                AudioFormatOption
            )
            from docling.datamodel.pipeline_options import AsrPipelineOptions
            from docling.datamodel import asr_model_specs
            from docling.datamodel.base_models import InputFormat
            from docling.pipeline.asr_pipeline import AsrPipeline

            audio_path = Path(file_path).resolve()
            logger.info(
                f"Transcribing audio file using Whisper Turbo: {audio_path.name}"
            )

            if not audio_path.exists():
                raise FileNotFoundError(f"Audio file not found: {audio_path}")

            pipeline_options = AsrPipelineOptions()
            pipeline_options.asr_options = asr_model_specs.WHISPER_TURBO

            converter = DocumentConverter(
                format_options={
                    InputFormat.AUDIO: AudioFormatOption(
                        pipeline_cls=AsrPipeline,
                        pipeline_options=pipeline_options,
                    )
                }
            )

            result = converter.convert(audio_path)

            markdown_content = result.document.export_to_markdown()
            logger.info(f"Successfully transcribed {os.path.basename(file_path)}")

            return (markdown_content, result.document)

        except Exception as e:
            logger.error(f"Failed to transcribe {file_path} with Whisper ASR: {e}")
            return (
                f"[Error: Could not transcribe audio file "
                f"{os.path.basename(file_path)}]",
                None
            )

    def _extract_title(self, content: str, file_path: str) -> str:
        """
        Extract title from document content or filename.

        Args:
            content: Document content
            file_path: Path to the document file

        Returns:
            Document title
        """
        lines = content.split('\n')
        for line in lines[:10]:
            line = line.strip()
            if line.startswith('# '):
                return line[2:].strip()

        return os.path.splitext(os.path.basename(file_path))[0]

    def _extract_document_metadata(
        self,
        content: str,
        file_path: str
    ) -> Dict[str, Any]:
        """
        Extract metadata from document content.

        Args:
            content: Document content
            file_path: Path to the document file

        Returns:
            Document metadata dictionary
        """
        metadata = {
            "file_path": file_path,
            "file_size": len(content),
            "ingestion_date": datetime.now().isoformat()
        }

        if content.startswith('---'):
            try:
                import yaml
                end_marker = content.find('\n---\n', 4)
                if end_marker != -1:
                    frontmatter = content[4:end_marker]
                    yaml_metadata = yaml.safe_load(frontmatter)
                    if isinstance(yaml_metadata, dict):
                        metadata.update(yaml_metadata)
            except ImportError:
                logger.warning(
                    "PyYAML not installed, skipping frontmatter extraction"
                )
            except Exception as e:
                logger.warning(f"Failed to parse frontmatter: {e}")

        lines = content.split('\n')
        metadata['line_count'] = len(lines)
        metadata['word_count'] = len(content.split())

        return metadata

    async def _save_to_mongodb(
        self,
        title: str,
        source: str,
        content: str,
        chunks: List[DocumentChunk],
        metadata: Dict[str, Any]
    ) -> str:
        """
        Save document and chunks to MongoDB.

        Args:
            title: Document title
            source: Document source path
            content: Document content
            chunks: List of document chunks with embeddings
            metadata: Document metadata

        Returns:
            Document ID (ObjectId as string)
        """
        documents_collection = self.db[
            self.settings.mongodb_collection_documents
        ]
        chunks_collection = self.db[self.settings.mongodb_collection_chunks]

        document_dict = {
            "title": title,
            "source": source,
            "content": content,
            "metadata": metadata,
            "created_at": datetime.now()
        }

        document_result = await documents_collection.insert_one(document_dict)
        document_id = document_result.inserted_id

        logger.info(f"Inserted document with ID: {document_id}")

        chunk_dicts = []
        for chunk in chunks:
            chunk_dict = {
                "document_id": document_id,
                "content": chunk.content,
                "embedding": chunk.embedding,
                "chunk_index": chunk.index,
                "metadata": chunk.metadata,
                "token_count": chunk.token_count,
                "created_at": datetime.now()
            }
            chunk_dicts.append(chunk_dict)

        if chunk_dicts:
            await chunks_collection.insert_many(chunk_dicts, ordered=False)
            logger.info(f"Inserted {len(chunk_dicts)} chunks")

        return str(document_id)

    async def _clean_databases(self) -> None:
        """Clean existing data from MongoDB collections."""
        logger.warning("Cleaning existing data from MongoDB...")

        documents_collection = self.db[
            self.settings.mongodb_collection_documents
        ]
        chunks_collection = self.db[self.settings.mongodb_collection_chunks]

        chunks_result = await chunks_collection.delete_many({})
        logger.info(f"Deleted {chunks_result.deleted_count} chunks")

        docs_result = await documents_collection.delete_many({})
        logger.info(f"Deleted {docs_result.deleted_count} documents")

    async def _ingest_single_document(self, file_path: str) -> IngestionResult:
        """
        Ingest a single document.

        Args:
            file_path: Path to the document file

        Returns:
            Ingestion result
        """
        start_time = datetime.now()

        document_content, docling_doc = self._read_document(file_path)
        document_title = self._extract_title(document_content, file_path)
        document_source = os.path.relpath(file_path, self.documents_folder)

        document_metadata = self._extract_document_metadata(
            document_content,
            file_path
        )

        logger.info(f"Processing document: {document_title}")

        chunks = await self.chunker.chunk_document(
            content=document_content,
            title=document_title,
            source=document_source,
            metadata=document_metadata,
            docling_doc=docling_doc
        )

        if not chunks:
            logger.warning(f"No chunks created for {document_title}")
            return IngestionResult(
                document_id="",
                title=document_title,
                chunks_created=0,
                processing_time_ms=(
                    datetime.now() - start_time
                ).total_seconds() * 1000,
                errors=["No chunks created"]
            )

        logger.info(f"Created {len(chunks)} chunks")

        embedded_chunks = await self.embedder.embed_chunks(chunks)
        logger.info(f"Generated embeddings for {len(embedded_chunks)} chunks")

        document_id = await self._save_to_mongodb(
            document_title,
            document_source,
            document_content,
            embedded_chunks,
            document_metadata
        )

        logger.info(f"Saved document to MongoDB with ID: {document_id}")

        processing_time = (
            datetime.now() - start_time
        ).total_seconds() * 1000

        return IngestionResult(
            document_id=document_id,
            title=document_title,
            chunks_created=len(chunks),
            processing_time_ms=processing_time,
            errors=[]
        )

    async def ingest_documents(
        self,
        progress_callback: Optional[callable] = None
    ) -> List[IngestionResult]:
        """
        Ingest all documents from the documents folder.

        Args:
            progress_callback: Optional callback for progress updates

        Returns:
            List of ingestion results
        """
        if not self._initialized:
            await self.initialize()

        if self.clean_before_ingest:
            await self._clean_databases()

        document_files = self._find_document_files()

        if not document_files:
            logger.warning(
                f"No supported document files found in {self.documents_folder}"
            )
            return []

        logger.info(f"Found {len(document_files)} document files to process")

        results = []

        for i, file_path in enumerate(document_files):
            try:
                logger.info(
                    f"Processing file {i+1}/{len(document_files)}: {file_path}"
                )

                result = await self._ingest_single_document(file_path)
                results.append(result)

                if progress_callback:
                    progress_callback(i + 1, len(document_files))

            except Exception as e:
                logger.exception(f"Failed to process {file_path}: {e}")
                results.append(IngestionResult(
                    document_id="",
                    title=os.path.basename(file_path),
                    chunks_created=0,
                    processing_time_ms=0,
                    errors=[str(e)]
                ))

        total_chunks = sum(r.chunks_created for r in results)
        total_errors = sum(len(r.errors) for r in results)

        logger.info(
            f"Ingestion complete: {len(results)} documents, "
            f"{total_chunks} chunks, {total_errors} errors"
        )

        return results


async def main() -> None:
    """Main function for running ingestion."""
    parser = argparse.ArgumentParser(
        description="Ingest documents into MongoDB vector database"
    )
    parser.add_argument(
        "--documents", "-d",
        default="documents",
        help="Documents folder path"
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Skip cleaning existing data before ingestion"
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Chunk size for splitting documents"
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=200,
        help="Chunk overlap size"
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=512,
        help="Maximum tokens per chunk for embeddings"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    config = IngestionConfig(
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        max_chunk_size=args.chunk_size * 2,
        max_tokens=args.max_tokens
    )

    pipeline = DocumentIngestionPipeline(
        config=config,
        documents_folder=args.documents,
        clean_before_ingest=not args.no_clean
    )

    def progress_callback(current: int, total: int) -> None:
        print(f"Progress: {current}/{total} documents processed")

    try:
        start_time = datetime.now()

        results = await pipeline.ingest_documents(progress_callback)

        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()

        print("\n" + "="*50)
        print("INGESTION SUMMARY")
        print("="*50)
        print(f"Documents processed: {len(results)}")
        print(f"Total chunks created: {sum(r.chunks_created for r in results)}")
        print(f"Total errors: {sum(len(r.errors) for r in results)}")
        print(f"Total processing time: {total_time:.2f} seconds")
        print()

        for result in results:
            status = "[OK]" if not result.errors else "[FAILED]"
            print(f"{status} {result.title}: {result.chunks_created} chunks")

            if result.errors:
                for error in result.errors:
                    print(f"  Error: {error}")

    except KeyboardInterrupt:
        print("\nIngestion interrupted by user")
    except Exception as e:
        logger.exception(f"Ingestion failed: {e}")
        raise
    finally:
        await pipeline.close()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/services/ingestion/
git commit -m "feat(api): add ingestion services (chunker, embedder, pipeline)

Adapted from MongoDB-RAG-Agent-main/src/ingestion/ with import paths
updated for layered structure."
```

---

## Task 7: FastAPI routers and main app (`apps/api/src/routers/`, `src/main.py`)

**Files:**
- Create: `apps/api/src/routers/__init__.py`
- Create: `apps/api/src/routers/health.py`
- Create: `apps/api/src/main.py`

- [ ] **Step 1: Create directory**

```bash
mkdir -p apps/api/src/routers
```

- [ ] **Step 2: Create `apps/api/src/routers/__init__.py`**

```python
"""API route handlers."""
```

- [ ] **Step 3: Create `apps/api/src/routers/health.py`**

```python
"""Health check endpoint."""

import logging

from fastapi import APIRouter
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from src.core.dependencies import AgentDependencies

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """
    Check API and MongoDB health.

    Returns 200 with status if healthy, 503 if MongoDB is unreachable.
    """
    deps = AgentDependencies()
    try:
        await deps.initialize()
        await deps.cleanup()
        return {"status": "ok", "mongodb": "connected"}
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logger.error(f"Health check failed: {e}")
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={"status": "error", "mongodb": "disconnected", "detail": str(e)}
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={"status": "error", "detail": str(e)}
        )
```

- [ ] **Step 4: Create `apps/api/src/main.py`**

```python
"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.dependencies import AgentDependencies
from src.routers.health import router as health_router

logger = logging.getLogger(__name__)

# Shared dependencies instance for app lifecycle
_deps = AgentDependencies()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and clean up application resources."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger.info("Starting MongoRAG API...")
    try:
        await _deps.initialize()
        logger.info("MongoRAG API started successfully")
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        # Don't crash — health endpoint will report the failure
    yield
    logger.info("Shutting down MongoRAG API...")
    await _deps.cleanup()


app = FastAPI(
    title="MongoRAG API",
    description="Multi-tenant RAG backend powered by MongoDB Atlas Vector Search",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3100"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router)
```

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/routers/ apps/api/src/main.py
git commit -m "feat(api): add FastAPI app with health check endpoint

App factory with CORS, lifespan (MongoDB init/cleanup), and GET /health
that verifies MongoDB connectivity."
```

---

## Task 8: CLI and pyproject.toml (`apps/api/`)

**Files:**
- Create: `apps/api/src/cli.py`
- Create: `apps/api/pyproject.toml`
- Create: `apps/api/.env.example`
- Create: `apps/api/tests/__init__.py`

- [ ] **Step 1: Create tests directory**

```bash
mkdir -p apps/api/tests
```

- [ ] **Step 2: Create `apps/api/src/cli.py`**

Adapted from reference — update imports:

```python
#!/usr/bin/env python3
"""Conversational CLI with real-time streaming and tool call visibility."""

import asyncio
from typing import List

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from pydantic_ai import Agent
from pydantic_ai.messages import PartDeltaEvent, PartStartEvent, TextPartDelta
from pydantic_ai.ag_ui import StateDeps
from dotenv import load_dotenv

from src.services.agent import rag_agent, RAGState
from src.core.settings import load_settings

# Load environment variables
load_dotenv(override=True)

console = Console()


async def stream_agent_interaction(
    user_input: str,
    message_history: List,
    deps: StateDeps[RAGState]
) -> tuple[str, List]:
    """
    Stream agent interaction with real-time tool call display.

    Args:
        user_input: The user's input text
        message_history: List of ModelRequest/ModelResponse objects
        deps: StateDeps with RAG state

    Returns:
        Tuple of (streamed_text, updated_message_history)
    """
    try:
        return await _stream_agent(user_input, deps, message_history)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        return ("", [])


async def _stream_agent(
    user_input: str,
    deps: StateDeps[RAGState],
    message_history: List
) -> tuple[str, List]:
    """Stream the agent execution and return response."""

    response_text = ""

    async with rag_agent.iter(
        user_input,
        deps=deps,
        message_history=message_history
    ) as run:

        async for node in run:

            if Agent.is_user_prompt_node(node):
                pass

            elif Agent.is_model_request_node(node):
                console.print("[bold blue]Assistant:[/bold blue] ", end="")

                async with node.stream(run.ctx) as request_stream:
                    async for event in request_stream:
                        if isinstance(event, PartStartEvent) and event.part.part_kind == 'text':
                            initial_text = event.part.content
                            if initial_text:
                                console.print(initial_text, end="")
                                response_text += initial_text

                        elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                            delta_text = event.delta.content_delta
                            if delta_text:
                                console.print(delta_text, end="")
                                response_text += delta_text

                console.print()

            elif Agent.is_call_tools_node(node):
                async with node.stream(run.ctx) as tool_stream:
                    async for event in tool_stream:
                        event_type = type(event).__name__

                        if event_type == "FunctionToolCallEvent":
                            tool_name = "Unknown Tool"
                            args = None

                            if hasattr(event, 'part'):
                                part = event.part

                                if hasattr(part, 'tool_name'):
                                    tool_name = part.tool_name
                                elif hasattr(part, 'function_name'):
                                    tool_name = part.function_name
                                elif hasattr(part, 'name'):
                                    tool_name = part.name

                                if hasattr(part, 'args'):
                                    args = part.args
                                elif hasattr(part, 'arguments'):
                                    args = part.arguments

                            console.print(f"  [cyan]Calling tool:[/cyan] [bold]{tool_name}[/bold]")

                            if args and isinstance(args, dict):
                                if 'query' in args:
                                    console.print(f"    [dim]Query:[/dim] {args['query']}")
                                if 'search_type' in args:
                                    console.print(f"    [dim]Type:[/dim] {args['search_type']}")
                                if 'match_count' in args:
                                    console.print(f"    [dim]Results:[/dim] {args['match_count']}")
                            elif args:
                                args_str = str(args)
                                if len(args_str) > 100:
                                    args_str = args_str[:97] + "..."
                                console.print(f"    [dim]Args: {args_str}[/dim]")

                        elif event_type == "FunctionToolResultEvent":
                            console.print(f"  [green]Search completed successfully[/green]")

            elif Agent.is_end_node(node):
                pass

    new_messages = run.result.new_messages()

    final_output = run.result.output if hasattr(run.result, 'output') else str(run.result)
    response = response_text.strip() or final_output

    return (response, new_messages)


def display_welcome():
    """Display welcome message with configuration info."""
    settings = load_settings()

    welcome = Panel(
        "[bold blue]MongoDB RAG Agent[/bold blue]\n\n"
        "[green]Intelligent knowledge base search with MongoDB Atlas Vector Search[/green]\n"
        f"[dim]LLM: {settings.llm_model}[/dim]\n\n"
        "[dim]Type 'exit' to quit, 'info' for system info, 'clear' to clear screen[/dim]",
        style="blue",
        padding=(1, 2)
    )
    console.print(welcome)
    console.print()


async def main():
    """Main conversation loop."""

    display_welcome()

    state = RAGState()

    deps = StateDeps[RAGState](state=state)

    console.print("[bold green]✓[/bold green] Search system initialized\n")

    message_history = []

    try:
        while True:
            try:
                user_input = Prompt.ask("[bold green]You").strip()

                if user_input.lower() in ['exit', 'quit', 'q']:
                    console.print("\n[yellow]Goodbye![/yellow]")
                    break

                elif user_input.lower() == 'info':
                    settings = load_settings()
                    console.print(Panel(
                        f"[cyan]LLM Provider:[/cyan] {settings.llm_provider}\n"
                        f"[cyan]LLM Model:[/cyan] {settings.llm_model}\n"
                        f"[cyan]Embedding Model:[/cyan] {settings.embedding_model}\n"
                        f"[cyan]Default Match Count:[/cyan] {settings.default_match_count}\n"
                        f"[cyan]Default Text Weight:[/cyan] {settings.default_text_weight}",
                        title="System Configuration",
                        border_style="magenta"
                    ))
                    continue

                elif user_input.lower() == 'clear':
                    console.clear()
                    display_welcome()
                    continue

                if not user_input:
                    continue

                response_text, new_messages = await stream_agent_interaction(
                    user_input,
                    message_history,
                    deps
                )

                message_history.extend(new_messages)

                console.print()

            except KeyboardInterrupt:
                console.print("\n[yellow]Use 'exit' to quit[/yellow]")
                continue

            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                import traceback
                traceback.print_exc()
                continue

    finally:
        console.print("\n[dim]Goodbye![/dim]")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Create `apps/api/pyproject.toml`**

```toml
[project]
name = "mongorag-api"
version = "0.1.0"
description = "Multi-tenant RAG backend powered by MongoDB Atlas Vector Search"
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.7.0",
    "pydantic-ai>=0.1.0",
    "pymongo>=4.10.0",
    "openai>=1.58.0",
    "docling>=2.14.0",
    "docling-core>=2.4.0",
    "transformers>=4.47.0",
    "rich>=13.9.0",
    "python-dotenv>=1.0.1",
    "aiofiles>=24.1.0",
    "openai-whisper>=20240930",
]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.uv]
dev-dependencies = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.27.0",
    "ruff>=0.8.0",
]

[tool.ruff]
target-version = "py310"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
    "unit: Unit tests (no external dependencies)",
    "integration: Integration tests (requires MongoDB, APIs)",
]
```

- [ ] **Step 4: Create `apps/api/.env.example`**

```bash
# MongoDB Atlas Configuration
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/?appName=YourAppName
MONGODB_DATABASE=rag_db
MONGODB_COLLECTION_DOCUMENTS=documents
MONGODB_COLLECTION_CHUNKS=chunks

# MongoDB Atlas Search Indexes (must match Atlas UI)
MONGODB_VECTOR_INDEX=vector_index
MONGODB_TEXT_INDEX=text_index

# LLM Provider Configuration
LLM_PROVIDER=openrouter
LLM_API_KEY=your-llm-api-key-here
LLM_MODEL=anthropic/claude-haiku-4.5
LLM_BASE_URL=https://openrouter.ai/api/v1

# Embedding Provider Configuration
EMBEDDING_PROVIDER=openai
EMBEDDING_API_KEY=your-openai-api-key-here
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_BASE_URL=https://api.openai.com/v1

# Search Configuration
DEFAULT_MATCH_COUNT=10
MAX_MATCH_COUNT=50
DEFAULT_TEXT_WEIGHT=0.3

# Application Settings
APP_ENV=development
LOG_LEVEL=INFO
```

- [ ] **Step 5: Create `apps/api/tests/__init__.py`**

```python
"""MongoRAG API tests."""
```

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/cli.py apps/api/pyproject.toml apps/api/.env.example apps/api/tests/
git commit -m "feat(api): add CLI, pyproject.toml, env template, and test scaffold

CLI adapted from reference app. pyproject.toml adds FastAPI/uvicorn
to reference app dependencies. Ruff and pytest configured."
```

---

## Task 9: Health endpoint test

**Files:**
- Create: `apps/api/tests/test_health.py`

- [ ] **Step 1: Create `apps/api/tests/test_health.py`**

```python
"""Tests for health check endpoint."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client with mocked dependencies."""
    with patch("src.main._deps") as mock_deps:
        mock_deps.initialize = AsyncMock()
        mock_deps.cleanup = AsyncMock()
        from src.main import app
        with TestClient(app) as c:
            yield c


@pytest.mark.unit
def test_health_returns_ok(client):
    """Health endpoint returns 200 when MongoDB is reachable."""
    with patch("src.routers.health.AgentDependencies") as MockDeps:
        instance = MockDeps.return_value
        instance.initialize = AsyncMock()
        instance.cleanup = AsyncMock()

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["mongodb"] == "connected"


@pytest.mark.unit
def test_health_returns_503_on_mongo_failure(client):
    """Health endpoint returns 503 when MongoDB is unreachable."""
    from pymongo.errors import ConnectionFailure

    with patch("src.routers.health.AgentDependencies") as MockDeps:
        instance = MockDeps.return_value
        instance.initialize = AsyncMock(side_effect=ConnectionFailure("Connection refused"))
        instance.cleanup = AsyncMock()

        response = client.get("/health")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "error"
```

- [ ] **Step 2: Run the test**

```bash
cd apps/api && uv sync && uv run pytest tests/test_health.py -v
```

Expected: Tests pass (or we fix until they pass).

- [ ] **Step 3: Commit**

```bash
git add apps/api/tests/test_health.py
git commit -m "test(api): add health endpoint unit tests

Tests verify 200 on healthy MongoDB and 503 on connection failure."
```

---

## Task 10: API Dockerfile

**Files:**
- Create: `apps/api/Dockerfile`

- [ ] **Step 1: Create `apps/api/Dockerfile`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml .

# Install dependencies
RUN uv sync --no-dev

# Copy source code
COPY src/ src/

# Expose port
EXPOSE 8100

# Run the application
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8100"]
```

- [ ] **Step 2: Commit**

```bash
git add apps/api/Dockerfile
git commit -m "chore(api): add Dockerfile

Python 3.11-slim with uv for dependency management."
```

---

## Task 11: Initialize Next.js app (`apps/web/`)

**Files:**
- Create: `apps/web/` (via create-next-app)
- Create: `apps/web/.env.example`

- [ ] **Step 1: Create Next.js app**

```bash
cd apps && pnpm create next-app@latest web \
  --typescript \
  --tailwind \
  --eslint \
  --app \
  --no-src-dir \
  --import-alias "@/*" \
  --use-pnpm \
  --no-turbopack
```

- [ ] **Step 2: Set port to 3100**

Edit `apps/web/package.json` — change the `dev` script:

In `scripts.dev`, change `"next dev"` to `"next dev --port 3100"`.

- [ ] **Step 3: Initialize shadcn/ui**

```bash
cd apps/web && pnpm dlx shadcn@latest init -d
```

This uses defaults (new-york style, zinc palette, CSS variables).

- [ ] **Step 4: Create `apps/web/.env.example`**

```bash
# API
NEXT_PUBLIC_API_URL=http://localhost:8100

# Stripe
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_your-key-here

# NextAuth.js
NEXTAUTH_SECRET=your-nextauth-secret-here
NEXTAUTH_URL=http://localhost:3100
```

- [ ] **Step 5: Commit**

```bash
git add apps/web/
git commit -m "feat(web): initialize Next.js app with TypeScript, Tailwind, shadcn/ui

App Router, port 3100, import alias @/*, shadcn/ui (new-york style)."
```

---

## Task 12: Web Dockerfile

**Files:**
- Create: `apps/web/Dockerfile`

- [ ] **Step 1: Create `apps/web/Dockerfile`**

```dockerfile
FROM node:22-alpine AS base

# Install pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

# Dependencies stage
FROM base AS deps
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Build stage
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm build

# Production stage
FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3100
ENV PORT=3100

CMD ["node", "server.js"]
```

- [ ] **Step 2: Add standalone output to next.config**

Edit the Next.js config file to add `output: "standalone"` so Docker builds produce a self-contained server.

- [ ] **Step 3: Commit**

```bash
git add apps/web/Dockerfile apps/web/next.config.*
git commit -m "chore(web): add Dockerfile with multi-stage build

Node 22 Alpine, pnpm, standalone output for minimal container."
```

---

## Task 13: Widget scaffold (`packages/widget/`)

**Files:**
- Create: `packages/widget/package.json`
- Create: `packages/widget/tsconfig.json`
- Create: `packages/widget/src/index.ts`

- [ ] **Step 1: Create directory**

```bash
mkdir -p packages/widget/src
```

- [ ] **Step 2: Create `packages/widget/package.json`**

```json
{
  "name": "@mongorag/widget",
  "version": "0.1.0",
  "description": "Embeddable chat widget for MongoRAG",
  "main": "dist/widget.js",
  "scripts": {
    "build": "esbuild src/index.ts --bundle --minify --outfile=dist/widget.js --format=iife --target=es2020",
    "dev": "esbuild src/index.ts --bundle --outfile=dist/widget.js --format=iife --target=es2020 --watch"
  },
  "devDependencies": {
    "esbuild": "^0.24.0",
    "typescript": "^5.7.0"
  }
}
```

- [ ] **Step 3: Create `packages/widget/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "outDir": "dist",
    "rootDir": "src",
    "declaration": true
  },
  "include": ["src"],
  "exclude": ["node_modules", "dist"]
}
```

- [ ] **Step 4: Create `packages/widget/src/index.ts`**

```typescript
/**
 * MongoRAG Embeddable Chat Widget
 *
 * Usage:
 *   <script src="https://cdn.mongorag.com/widget.js"
 *           data-api-key="mrag_..." />
 */

interface MongoRAGConfig {
  apiKey: string;
  apiUrl?: string;
}

function init(): void {
  const script = document.currentScript as HTMLScriptElement | null;
  if (!script) return;

  const config: MongoRAGConfig = {
    apiKey: script.dataset.apiKey || "",
    apiUrl: script.dataset.apiUrl || "",
  };

  if (!config.apiKey) {
    console.warn("[MongoRAG] Missing data-api-key attribute");
    return;
  }

  console.log("[MongoRAG] Widget initialized", { apiUrl: config.apiUrl });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
```

- [ ] **Step 5: Commit**

```bash
git add packages/widget/
git commit -m "feat(widget): scaffold embeddable chat widget with esbuild

Minimal TypeScript scaffold with esbuild bundler, IIFE output,
script-tag initialization pattern."
```

---

## Task 14: Docker Compose, Makefile, root files

**Files:**
- Create: `docker-compose.yml`
- Create: `Makefile`
- Create: `.env.example`
- Create: `README.md`

- [ ] **Step 1: Create `docker-compose.yml`**

```yaml
services:
  api:
    build: ./apps/api
    ports:
      - "8100:8100"
    env_file:
      - ./apps/api/.env
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8100/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  web:
    build: ./apps/web
    ports:
      - "3100:3100"
    env_file:
      - ./apps/web/.env.local
    depends_on:
      api:
        condition: service_healthy
```

- [ ] **Step 2: Create `Makefile`**

```makefile
.PHONY: dev api web install lint test widget-build clean

# Run both API and web dev servers concurrently
dev:
	@echo "Starting API and Web dev servers..."
	@make -j2 api web

# Run FastAPI dev server
api:
	cd apps/api && uv run uvicorn src.main:app --reload --port 8100

# Run Next.js dev server
web:
	cd apps/web && pnpm dev

# Install all dependencies
install:
	cd apps/api && uv sync
	cd apps/web && pnpm install
	cd packages/widget && pnpm install

# Run all linters
lint:
	cd apps/api && uv run ruff check .
	cd apps/web && pnpm lint

# Run all tests
test:
	cd apps/api && uv run pytest
	cd apps/web && pnpm test

# Build widget
widget-build:
	cd packages/widget && pnpm build

# Clean build artifacts
clean:
	rm -rf apps/api/.venv apps/api/build apps/api/dist
	rm -rf apps/web/.next apps/web/node_modules
	rm -rf packages/widget/dist packages/widget/node_modules
```

- [ ] **Step 3: Create root `.env.example`**

```bash
# MongoRAG Environment Configuration
#
# Environment variables are managed per-app:
#
#   Backend (FastAPI):  apps/api/.env
#   Frontend (Next.js): apps/web/.env.local
#
# Copy the .env.example in each app directory and fill in your values.
# See README.md for setup instructions.
```

- [ ] **Step 4: Create `README.md`**

```markdown
# MongoRAG

Multi-tenant AI chatbot SaaS powered by RAG. Upload documents, get an embeddable chatbot that answers questions grounded in your own data.

## Architecture

- **apps/api** — FastAPI backend (Python, Pydantic AI, MongoDB Atlas Vector Search)
- **apps/web** — Next.js frontend (TypeScript, Tailwind CSS, shadcn/ui)
- **packages/widget** — Embeddable JS chat widget

## Prerequisites

- [Python 3.10+](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/) — Python package manager
- [Node.js 22+](https://nodejs.org/)
- [pnpm](https://pnpm.io/) — Node package manager
- [MongoDB Atlas](https://www.mongodb.com/atlas) account (free M0 tier works)

## Quick Start

### 1. Install dependencies

```bash
make install
```

### 2. Configure environment

```bash
# Backend
cp apps/api/.env.example apps/api/.env
# Edit apps/api/.env with your MongoDB URI and API keys

# Frontend
cp apps/web/.env.example apps/web/.env.local
# Edit apps/web/.env.local with your API URL
```

### 3. Run dev servers

```bash
make dev
```

This starts:
- API at http://localhost:8100
- Web at http://localhost:3100

### Individual services

```bash
make api    # FastAPI only
make web    # Next.js only
```

## Other Commands

```bash
make lint          # Run linters (ruff + eslint)
make test          # Run test suites
make widget-build  # Build the embeddable widget
make clean         # Remove build artifacts
```

## Docker

```bash
# Copy env files first (see step 2 above)
docker compose up --build
```

## Project Structure

```
mongo-rag/
├── apps/
│   ├── api/          # FastAPI backend
│   │   ├── src/
│   │   │   ├── core/       # Settings, dependencies, providers
│   │   │   ├── models/     # Pydantic models
│   │   │   ├── routers/    # API endpoints
│   │   │   ├── services/   # Business logic (agent, search, ingestion)
│   │   │   └── main.py     # App factory
│   │   └── tests/
│   └── web/          # Next.js frontend
├── packages/
│   └── widget/       # Embeddable chat widget
├── docs/             # Architecture, roadmap, plans
├── Makefile          # Dev scripts
└── docker-compose.yml
```

## Documentation

- [Architecture](docs/architecture.md)
- [Roadmap](docs/ROADMAP.md)
```

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml Makefile .env.example README.md
git commit -m "chore: add Docker Compose, Makefile, env template, and README

Docker Compose with api + web services (Atlas for MongoDB).
Makefile with dev, install, lint, test, widget-build targets.
README with setup instructions."
```

---

## Task 15: Verify and final commit

- [ ] **Step 1: Verify directory structure**

```bash
find apps packages -type f -not -path '*/node_modules/*' -not -path '*/.next/*' -not -path '*/__pycache__/*' -not -path '*/.venv/*' | sort
```

Expected: All files from the design are present.

- [ ] **Step 2: Verify API starts (syntax check)**

```bash
cd apps/api && uv sync && uv run python -c "from src.main import app; print('FastAPI app OK')"
```

Expected: Prints "FastAPI app OK" (may warn about missing .env — that's fine).

- [ ] **Step 3: Verify Next.js builds**

```bash
cd apps/web && pnpm install && pnpm build
```

Expected: Build succeeds.

- [ ] **Step 4: Verify widget builds**

```bash
cd packages/widget && pnpm install && pnpm build
```

Expected: `dist/widget.js` created.

- [ ] **Step 5: Run API tests**

```bash
cd apps/api && uv run pytest tests/ -v
```

Expected: Health check tests pass.

- [ ] **Step 6: Run API linter**

```bash
cd apps/api && uv run ruff check .
```

Expected: No errors (or fix any that appear).

- [ ] **Step 7: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: address lint and build issues from verification"
```

Only if there were fixes needed.
