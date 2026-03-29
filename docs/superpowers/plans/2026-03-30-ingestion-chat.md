# Ingestion Pipeline & RAG Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement document ingestion (Celery + Redis) and RAG chat (REST + SSE + WebSocket) endpoints with tenant isolation for MongoRAG.

**Architecture:** FastAPI endpoints dispatch ingestion to Celery workers via Redis. Chat uses shared service layer: hybrid search filtered by tenant_id, Pydantic AI agent for LLM, conversation persistence in MongoDB. Two transport layers for chat: SSE (REST API) and WebSocket (widget).

**Tech Stack:** FastAPI, Celery, Redis, MongoDB (pymongo async), Pydantic AI, OpenAI embeddings, Docling, SSE (starlette StreamingResponse), WebSocket (FastAPI native)

**Branch:** `feature/rag-ingestion-chat`

**Design doc:** `docs/plans/2026-03-30-ingestion-chat-design.md`

---

## File Map

### New Files

| File | Responsibility |
|------|---------------|
| `src/core/tenant.py` | FastAPI dependency: extract `X-Tenant-ID` header, validate tenant exists |
| `src/worker.py` | Celery app config + `ingest_document` task |
| `src/services/ingestion/service.py` | Tenant-aware ingestion service (wraps pipeline for API/Celery use) |
| `src/services/conversation.py` | Conversation CRUD (get_or_create, append_message, get_history) |
| `src/services/chat.py` | Shared chat orchestration (search + prompt + LLM stream) |
| `src/routers/ingest.py` | `POST /api/v1/documents/ingest`, `GET /api/v1/documents/{id}/status` |
| `src/routers/chat.py` | `POST /api/v1/chat` (JSON + SSE), `WS /api/v1/chat/ws` |
| `src/models/api.py` | Request/response Pydantic models for API endpoints |
| `tests/test_tenant.py` | Tests for tenant dependency |
| `tests/test_ingest_router.py` | Tests for ingestion endpoint |
| `tests/test_ingestion_service.py` | Tests for tenant-aware ingestion service |
| `tests/test_conversation.py` | Tests for conversation service |
| `tests/test_chat_router.py` | Tests for chat endpoint |
| `tests/test_search_tenant.py` | Tests for tenant-filtered search |
| `tests/conftest.py` | Shared test fixtures (mock deps, test client, tenant_id) |

### Modified Files

| File | Changes |
|------|---------|
| `pyproject.toml` | Add `celery[redis]`, `redis` dependencies |
| `.env.example` | Add `REDIS_URL` |
| `src/core/settings.py` | Add `redis_url`, `max_upload_size_mb`, `upload_temp_dir` settings |
| `src/core/prompts.py` | Versioned template with `{product_name}` placeholder |
| `src/services/search.py` | Add `tenant_id` param to all search functions, add filter stages |
| `src/services/agent.py` | Refactor to accept deps + tenant_id from caller, remove self-created connections |
| `src/main.py` | Register ingest + chat routers, expose shared deps |
| `src/models/document.py` | Add `status` field to DocumentModel |

---

## Task 1: Dependencies & Configuration

**Files:**
- Modify: `apps/api/pyproject.toml`
- Modify: `apps/api/.env.example`
- Modify: `apps/api/src/core/settings.py`

- [ ] **Step 1: Add celery and redis to pyproject.toml**

In `apps/api/pyproject.toml`, add to the `dependencies` list:

```toml
    "celery[redis]>=5.4.0",
    "redis>=5.0.0",
    "python-multipart>=0.0.9",
```

- [ ] **Step 2: Add REDIS_URL to .env.example**

Append to `apps/api/.env.example`:

```
# Redis Configuration (Celery broker)
REDIS_URL=redis://localhost:6379/0
```

- [ ] **Step 3: Add new settings fields**

In `apps/api/src/core/settings.py`, add these fields to the `Settings` class after the search config section:

```python
    # Redis / Celery Configuration
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for Celery broker and result backend",
    )

    # Upload Configuration
    max_upload_size_mb: int = Field(default=50, description="Maximum file upload size in MB")

    upload_temp_dir: str = Field(
        default="/tmp/mongorag-uploads", description="Temporary directory for uploaded files"
    )
```

- [ ] **Step 4: Install dependencies**

Run: `cd apps/api && uv sync`
Expected: Dependencies install successfully, including celery and redis.

- [ ] **Step 5: Commit**

```bash
git add apps/api/pyproject.toml apps/api/.env.example apps/api/src/core/settings.py apps/api/uv.lock
git commit -m "chore: add celery, redis, multipart dependencies and config"
```

---

## Task 2: Document Status Field & API Models

**Files:**
- Modify: `apps/api/src/models/document.py`
- Create: `apps/api/src/models/api.py`

- [ ] **Step 1: Add status enum and field to DocumentModel**

In `apps/api/src/models/document.py`, add a `DocumentStatus` enum and a `status` field:

```python
from enum import Enum

class DocumentStatus(str, Enum):
    """Document processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
```

Add to `DocumentModel` class, after `etag_or_commit`:

```python
    status: str = Field(default=DocumentStatus.PENDING, description="Processing status")
    error_message: Optional[str] = Field(default=None, description="Error details if status is failed")
    chunk_count: int = Field(default=0, description="Number of chunks created")
```

- [ ] **Step 2: Create API request/response models**

Create `apps/api/src/models/api.py`:

```python
"""Request and response models for API endpoints."""

from typing import Optional

from pydantic import BaseModel, Field


# --- Ingestion ---

class IngestResponse(BaseModel):
    """Response from document ingestion endpoint."""
    document_id: str = Field(..., description="MongoDB document ID")
    status: str = Field(..., description="Processing status")
    task_id: str = Field(..., description="Celery task ID for tracking")


class DocumentStatusResponse(BaseModel):
    """Response from document status endpoint."""
    document_id: str
    status: str
    chunk_count: int = 0
    version: int = 1
    error_message: Optional[str] = None


# --- Chat ---

class ChatRequest(BaseModel):
    """Request body for chat endpoint."""
    message: str = Field(..., min_length=1, max_length=10000, description="User message")
    conversation_id: Optional[str] = Field(default=None, description="Existing conversation ID")
    search_type: str = Field(default="hybrid", description="Search type: semantic, text, hybrid")


class SourceReference(BaseModel):
    """A source document referenced in a chat response."""
    document_title: str
    heading_path: list[str] = Field(default_factory=list)
    snippet: str


class ChatResponse(BaseModel):
    """Response from chat endpoint (non-streaming)."""
    answer: str
    sources: list[SourceReference] = Field(default_factory=list)
    conversation_id: str


# --- WebSocket ---

class WSMessage(BaseModel):
    """Incoming WebSocket message from client."""
    type: str = Field(..., description="Message type: message, cancel")
    content: Optional[str] = Field(default=None, description="Message content")
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID")
```

- [ ] **Step 3: Commit**

```bash
git add apps/api/src/models/document.py apps/api/src/models/api.py
git commit -m "feat: add document status enum and API request/response models"
```

---

## Task 3: Tenant Dependency

**Files:**
- Create: `apps/api/src/core/tenant.py`
- Create: `apps/api/tests/conftest.py`
- Create: `apps/api/tests/test_tenant.py`

- [ ] **Step 1: Write the failing test for tenant extraction**

Create `apps/api/tests/conftest.py`:

```python
"""Shared test fixtures."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_deps():
    """Create mock AgentDependencies."""
    deps = MagicMock()
    deps.initialize = AsyncMock()
    deps.cleanup = AsyncMock()
    deps.db = MagicMock()
    deps.settings = MagicMock()
    deps.tenants_collection = MagicMock()
    deps.documents_collection = MagicMock()
    deps.chunks_collection = MagicMock()
    deps.conversations_collection = MagicMock()
    return deps


@pytest.fixture
def client(mock_deps):
    """Create test client with mocked dependencies."""
    with patch("src.main._deps", mock_deps):
        from src.main import app
        with TestClient(app) as c:
            yield c


MOCK_TENANT_ID = "test-tenant-001"
```

Create `apps/api/tests/test_tenant.py`:

```python
"""Tests for tenant dependency."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from tests.conftest import MOCK_TENANT_ID


@pytest.mark.unit
def test_missing_tenant_header_returns_400():
    """Request without X-Tenant-ID header returns 400."""
    from src.core.tenant import get_tenant_id

    app = FastAPI()

    @app.get("/test")
    async def test_endpoint(tenant_id: str = Depends(get_tenant_id)):
        return {"tenant_id": tenant_id}

    client = TestClient(app)
    response = client.get("/test")
    assert response.status_code == 400
    assert "X-Tenant-ID" in response.json()["detail"]


@pytest.mark.unit
def test_valid_tenant_header_returns_tenant_id():
    """Request with valid X-Tenant-ID header extracts tenant_id."""
    from src.core.tenant import get_tenant_id

    app = FastAPI()

    @app.get("/test")
    async def test_endpoint(tenant_id: str = Depends(get_tenant_id)):
        return {"tenant_id": tenant_id}

    client = TestClient(app)
    response = client.get("/test", headers={"X-Tenant-ID": MOCK_TENANT_ID})
    assert response.status_code == 200
    assert response.json()["tenant_id"] == MOCK_TENANT_ID


@pytest.mark.unit
def test_empty_tenant_header_returns_400():
    """Request with empty X-Tenant-ID header returns 400."""
    from src.core.tenant import get_tenant_id

    app = FastAPI()

    @app.get("/test")
    async def test_endpoint(tenant_id: str = Depends(get_tenant_id)):
        return {"tenant_id": tenant_id}

    client = TestClient(app)
    response = client.get("/test", headers={"X-Tenant-ID": ""})
    assert response.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && uv run pytest tests/test_tenant.py -v`
Expected: FAIL — `src.core.tenant` module does not exist.

- [ ] **Step 3: Implement tenant dependency**

Create `apps/api/src/core/tenant.py`:

```python
"""Tenant extraction dependency for FastAPI."""

from typing import Optional

from fastapi import Header, HTTPException


async def get_tenant_id(
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
) -> str:
    """Extract and validate tenant_id from X-Tenant-ID header.

    This is a stub for Phase 3 auth. The real implementation will
    derive tenant_id from the authenticated session or API key.

    Args:
        x_tenant_id: Tenant ID from request header.

    Returns:
        Validated tenant_id string.

    Raises:
        HTTPException: 400 if header is missing or empty.
    """
    if not x_tenant_id or not x_tenant_id.strip():
        raise HTTPException(
            status_code=400,
            detail="X-Tenant-ID header is required",
        )
    return x_tenant_id.strip()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/api && uv run pytest tests/test_tenant.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/core/tenant.py apps/api/tests/conftest.py apps/api/tests/test_tenant.py
git commit -m "feat: add X-Tenant-ID header extraction dependency with tests"
```

---

## Task 4: Tenant-Filtered Search

**Files:**
- Modify: `apps/api/src/services/search.py`
- Create: `apps/api/tests/test_search_tenant.py`

- [ ] **Step 1: Write failing test for tenant-filtered semantic search**

Create `apps/api/tests/test_search_tenant.py`:

```python
"""Tests for tenant-filtered search functions."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.search import SearchResult


def _make_mock_ctx(tenant_id: str, results: list[dict]) -> MagicMock:
    """Create a mock RunContext with deps for search functions."""
    ctx = MagicMock()
    ctx.deps = MagicMock()
    ctx.deps.settings = MagicMock()
    ctx.deps.settings.default_match_count = 10
    ctx.deps.settings.max_match_count = 50
    ctx.deps.settings.mongodb_vector_index = "vector_index"
    ctx.deps.settings.mongodb_text_index = "text_index"
    ctx.deps.settings.mongodb_collection_documents = "documents"
    ctx.deps.settings.mongodb_collection_chunks = "chunks"

    # Mock embedding
    ctx.deps.get_embedding = AsyncMock(return_value=[0.1] * 1536)

    # Mock collection with async cursor
    mock_collection = MagicMock()

    async def mock_aggregate(pipeline):
        """Return an async iterator over results."""
        class AsyncCursor:
            def __init__(self, data):
                self._data = data
                self._index = 0
            def __aiter__(self):
                return self
            async def __anext__(self):
                if self._index >= len(self._data):
                    raise StopAsyncIteration
                item = self._data[self._index]
                self._index += 1
                return item
        return AsyncCursor(results)

    mock_collection.aggregate = mock_aggregate
    ctx.deps.db = {
        "chunks": mock_collection,
    }
    ctx.deps.db.__getitem__ = lambda self, key: mock_collection

    return ctx


@pytest.mark.unit
async def test_semantic_search_includes_tenant_filter():
    """semantic_search passes tenant_id to $vectorSearch filter."""
    from src.services.search import semantic_search

    captured_pipelines = []
    mock_collection = MagicMock()

    async def capture_aggregate(pipeline):
        captured_pipelines.append(pipeline)
        class EmptyCursor:
            def __aiter__(self):
                return self
            async def __anext__(self):
                raise StopAsyncIteration
        return EmptyCursor()

    mock_collection.aggregate = capture_aggregate

    ctx = MagicMock()
    ctx.deps = MagicMock()
    ctx.deps.settings = MagicMock()
    ctx.deps.settings.default_match_count = 10
    ctx.deps.settings.max_match_count = 50
    ctx.deps.settings.mongodb_vector_index = "vector_index"
    ctx.deps.settings.mongodb_collection_documents = "documents"
    ctx.deps.settings.mongodb_collection_chunks = "chunks"
    ctx.deps.get_embedding = AsyncMock(return_value=[0.1] * 1536)
    ctx.deps.db = MagicMock()
    ctx.deps.db.__getitem__ = MagicMock(return_value=mock_collection)

    results = await semantic_search(ctx, "test query", tenant_id="tenant-abc")

    assert len(captured_pipelines) == 1
    pipeline = captured_pipelines[0]
    vector_stage = pipeline[0]["$vectorSearch"]
    assert vector_stage["filter"] == {"tenant_id": "tenant-abc"}


@pytest.mark.unit
async def test_text_search_includes_tenant_filter():
    """text_search passes tenant_id to $search compound filter."""
    from src.services.search import text_search

    captured_pipelines = []
    mock_collection = MagicMock()

    async def capture_aggregate(pipeline):
        captured_pipelines.append(pipeline)
        class EmptyCursor:
            def __aiter__(self):
                return self
            async def __anext__(self):
                raise StopAsyncIteration
        return EmptyCursor()

    mock_collection.aggregate = capture_aggregate

    ctx = MagicMock()
    ctx.deps = MagicMock()
    ctx.deps.settings = MagicMock()
    ctx.deps.settings.default_match_count = 10
    ctx.deps.settings.max_match_count = 50
    ctx.deps.settings.mongodb_text_index = "text_index"
    ctx.deps.settings.mongodb_collection_documents = "documents"
    ctx.deps.settings.mongodb_collection_chunks = "chunks"
    ctx.deps.db = MagicMock()
    ctx.deps.db.__getitem__ = MagicMock(return_value=mock_collection)

    results = await text_search(ctx, "test query", tenant_id="tenant-abc")

    assert len(captured_pipelines) == 1
    pipeline = captured_pipelines[0]
    search_stage = pipeline[0]["$search"]
    assert "compound" in search_stage
    filter_clause = search_stage["compound"]["filter"]
    assert any(
        f.get("equals", {}).get("value") == "tenant-abc"
        for f in filter_clause
    )


@pytest.mark.unit
async def test_search_without_tenant_id_raises():
    """Search functions require tenant_id parameter."""
    from src.services.search import semantic_search

    ctx = MagicMock()
    with pytest.raises(TypeError):
        await semantic_search(ctx, "test query")  # Missing tenant_id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && uv run pytest tests/test_search_tenant.py -v`
Expected: FAIL — `semantic_search` and `text_search` don't accept `tenant_id` parameter.

- [ ] **Step 3: Add tenant_id parameter to search functions**

Modify `apps/api/src/services/search.py`:

For `semantic_search`, change signature to add `tenant_id: str` as a required parameter (no default), and add filter to the `$vectorSearch` stage:

```python
async def semantic_search(
    ctx: RunContext[AgentDependencies], query: str, tenant_id: str, match_count: Optional[int] = None
) -> List[SearchResult]:
```

In the `$vectorSearch` pipeline stage, add the filter field:

```python
            {
                "$vectorSearch": {
                    "index": deps.settings.mongodb_vector_index,
                    "queryVector": query_embedding,
                    "path": "embedding",
                    "numCandidates": 100,
                    "limit": match_count,
                    "filter": {"tenant_id": tenant_id},
                }
            },
```

For `text_search`, change signature similarly and replace the `$search` stage with a compound query:

```python
async def text_search(
    ctx: RunContext[AgentDependencies], query: str, tenant_id: str, match_count: Optional[int] = None
) -> List[SearchResult]:
```

Replace the `$search` stage:

```python
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
                        "filter": [
                            {"equals": {"path": "tenant_id", "value": tenant_id}}
                        ],
                    },
                }
            },
```

For `hybrid_search`, add `tenant_id: str` parameter and pass it through to both sub-searches:

```python
async def hybrid_search(
    ctx: RunContext[AgentDependencies],
    query: str,
    tenant_id: str,
    match_count: Optional[int] = None,
    text_weight: Optional[float] = None,
) -> List[SearchResult]:
```

Update the `asyncio.gather` call:

```python
        semantic_results, text_results = await asyncio.gather(
            semantic_search(ctx, query, tenant_id, fetch_count),
            text_search(ctx, query, tenant_id, fetch_count),
            return_exceptions=True,
        )
```

And update the fallback at the bottom:

```python
            return await semantic_search(ctx, query, tenant_id, match_count)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/api && uv run pytest tests/test_search_tenant.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/services/search.py apps/api/tests/test_search_tenant.py
git commit -m "feat: add tenant_id filtering to all search functions"
```

---

## Task 5: Agent Refactor

**Files:**
- Modify: `apps/api/src/services/agent.py`
- Modify: `apps/api/src/core/prompts.py`

- [ ] **Step 1: Update system prompt to versioned template**

Replace the entire content of `apps/api/src/core/prompts.py`:

```python
"""Versioned system prompt templates for RAG agent."""

# ruff: noqa: E501

SYSTEM_PROMPT_V1 = """You are a documentation assistant for {product_name}.

## Rules:
1. Use ONLY the provided source snippets to answer questions.
2. If the sources are insufficient, say so clearly — do not hallucinate.
3. Include citations as [source_title#section] when referencing specific documents.
4. Do not invent APIs, flags, configuration options, or default values.
5. Be concise and direct.

## When to search:
- Questions about {product_name} documentation, features, or configuration → search the knowledge base
- Greetings, general conversation → respond directly without searching
- Questions outside {product_name} scope → say you can only help with {product_name} topics

## Search strategy:
- Use hybrid search (default) for most queries
- Start with 5-10 results for focused answers
"""

# Current active version
SYSTEM_PROMPT_TEMPLATE = SYSTEM_PROMPT_V1
SYSTEM_PROMPT_VERSION = "v1"


def build_system_prompt(product_name: str = "this product") -> str:
    """Build system prompt with tenant-specific product name.

    Args:
        product_name: The tenant's product name for personalization.

    Returns:
        Formatted system prompt string.
    """
    return SYSTEM_PROMPT_TEMPLATE.format(product_name=product_name)
```

- [ ] **Step 2: Refactor agent to accept deps from caller**

Replace the entire content of `apps/api/src/services/agent.py`:

```python
"""RAG agent with tenant-aware search."""

import logging
from typing import Optional

from pydantic_ai import Agent

from src.core.dependencies import AgentDependencies
from src.core.prompts import build_system_prompt
from src.core.providers import get_llm_model
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
) -> list:
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
    # Create a lightweight context wrapper for search functions
    class DepsContext:
        def __init__(self, d: AgentDependencies):
            self.deps = d

    ctx = DepsContext(deps)

    if search_type == "semantic":
        return await semantic_search(ctx, query, tenant_id, match_count)
    elif search_type == "text":
        return await text_search(ctx, query, tenant_id, match_count)
    else:
        return await hybrid_search(ctx, query, tenant_id, match_count)


def format_search_context(results: list) -> str:
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
        parts.append(
            f"[Source {i}: {result.document_title}]\n{heading}{result.content}"
        )
    return "\n\n---\n\n".join(parts)
```

- [ ] **Step 3: Commit**

```bash
git add apps/api/src/services/agent.py apps/api/src/core/prompts.py
git commit -m "refactor: make agent tenant-aware with versioned prompt templates"
```

---

## Task 6: Conversation Service

**Files:**
- Create: `apps/api/src/services/conversation.py`
- Create: `apps/api/tests/test_conversation.py`

- [ ] **Step 1: Write failing test for conversation service**

Create `apps/api/tests/test_conversation.py`:

```python
"""Tests for conversation service."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.conversation import ChatMessage, MessageRole


@pytest.mark.unit
async def test_get_or_create_new_conversation():
    """Creates a new conversation when no conversation_id is provided."""
    from src.services.conversation import ConversationService

    mock_collection = MagicMock()
    mock_collection.insert_one = AsyncMock(
        return_value=MagicMock(inserted_id="new-conv-id")
    )

    service = ConversationService(mock_collection)
    conv = await service.get_or_create("tenant-1", conversation_id=None)

    assert conv["tenant_id"] == "tenant-1"
    assert "session_id" in conv
    mock_collection.insert_one.assert_called_once()


@pytest.mark.unit
async def test_get_or_create_existing_conversation():
    """Returns existing conversation when conversation_id is provided and matches tenant."""
    from src.services.conversation import ConversationService

    existing = {
        "_id": "existing-conv-id",
        "tenant_id": "tenant-1",
        "session_id": "sess-123",
        "messages": [],
    }
    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(return_value=existing)

    service = ConversationService(mock_collection)
    conv = await service.get_or_create("tenant-1", conversation_id="existing-conv-id")

    assert conv["_id"] == "existing-conv-id"
    mock_collection.find_one.assert_called_once()


@pytest.mark.unit
async def test_get_or_create_wrong_tenant_returns_none():
    """Returns None when conversation_id exists but belongs to different tenant."""
    from src.services.conversation import ConversationService

    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(return_value=None)  # Filtered by tenant_id

    service = ConversationService(mock_collection)
    conv = await service.get_or_create("tenant-2", conversation_id="other-tenant-conv")

    assert conv is None


@pytest.mark.unit
async def test_append_message():
    """Appends a message to a conversation."""
    from src.services.conversation import ConversationService

    mock_collection = MagicMock()
    mock_collection.update_one = AsyncMock()

    service = ConversationService(mock_collection)
    message = ChatMessage(role=MessageRole.USER, content="Hello")

    await service.append_message("conv-1", "tenant-1", message)

    mock_collection.update_one.assert_called_once()
    call_args = mock_collection.update_one.call_args
    assert call_args[0][0] == {"_id": "conv-1", "tenant_id": "tenant-1"}


@pytest.mark.unit
async def test_get_history():
    """Retrieves last N messages from a conversation."""
    from src.services.conversation import ConversationService

    messages = [
        {"role": "user", "content": "msg1", "sources": [], "timestamp": "2026-01-01T00:00:00Z"},
        {"role": "assistant", "content": "msg2", "sources": [], "timestamp": "2026-01-01T00:01:00Z"},
    ]
    existing = {"_id": "conv-1", "tenant_id": "t1", "messages": messages}

    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(return_value=existing)

    service = ConversationService(mock_collection)
    history = await service.get_history("conv-1", "t1", limit=10)

    assert len(history) == 2
    assert history[0]["content"] == "msg1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && uv run pytest tests/test_conversation.py -v`
Expected: FAIL — `src.services.conversation` module does not exist.

- [ ] **Step 3: Implement conversation service**

Create `apps/api/src/services/conversation.py`:

```python
"""Conversation CRUD service."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pymongo.asynchronous.collection import AsyncCollection

from src.models.conversation import ChatMessage

logger = logging.getLogger(__name__)


class ConversationService:
    """Manages conversation persistence in MongoDB."""

    def __init__(self, collection: AsyncCollection) -> None:
        self.collection = collection

    async def get_or_create(
        self,
        tenant_id: str,
        conversation_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Get existing conversation or create a new one.

        Args:
            tenant_id: Tenant ID for isolation.
            conversation_id: Existing conversation ID, or None to create new.

        Returns:
            Conversation document dict, or None if conversation_id provided
            but not found for this tenant (cross-tenant access attempt).
        """
        if conversation_id:
            conv = await self.collection.find_one(
                {"_id": conversation_id, "tenant_id": tenant_id}
            )
            if conv is None:
                return None
            return conv

        now = datetime.now(timezone.utc)
        new_conv = {
            "_id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "session_id": str(uuid.uuid4()),
            "messages": [],
            "metadata": {},
            "created_at": now,
            "updated_at": now,
        }
        await self.collection.insert_one(new_conv)
        return new_conv

    async def append_message(
        self, conversation_id: str, tenant_id: str, message: ChatMessage
    ) -> None:
        """Append a message to a conversation.

        Args:
            conversation_id: Conversation to append to.
            tenant_id: Tenant ID for isolation.
            message: ChatMessage to append.
        """
        await self.collection.update_one(
            {"_id": conversation_id, "tenant_id": tenant_id},
            {
                "$push": {"messages": message.model_dump(mode="json")},
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
        )

    async def get_history(
        self, conversation_id: str, tenant_id: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get recent messages from a conversation.

        Args:
            conversation_id: Conversation to fetch from.
            tenant_id: Tenant ID for isolation.
            limit: Max number of recent messages to return.

        Returns:
            List of message dicts (most recent last), empty if not found.
        """
        conv = await self.collection.find_one(
            {"_id": conversation_id, "tenant_id": tenant_id}
        )
        if not conv:
            return []
        messages = conv.get("messages", [])
        return messages[-limit:]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/api && uv run pytest tests/test_conversation.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/services/conversation.py apps/api/tests/test_conversation.py
git commit -m "feat: add conversation CRUD service with tests"
```

---

## Task 7: Tenant-Aware Ingestion Service

**Files:**
- Create: `apps/api/src/services/ingestion/service.py`
- Create: `apps/api/tests/test_ingestion_service.py`

- [ ] **Step 1: Write failing tests for ingestion service**

Create `apps/api/tests/test_ingestion_service.py`:

```python
"""Tests for tenant-aware ingestion service."""

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.unit
async def test_create_pending_document():
    """create_pending_document inserts a document with status pending and tenant_id."""
    from src.services.ingestion.service import IngestionService

    mock_docs = MagicMock()
    mock_docs.insert_one = AsyncMock(
        return_value=MagicMock(inserted_id="doc-123")
    )

    service = IngestionService(documents_collection=mock_docs, chunks_collection=MagicMock())
    doc_id = await service.create_pending_document(
        tenant_id="tenant-1",
        title="Test Doc",
        source="test.pdf",
    )

    assert doc_id == "doc-123"
    call_args = mock_docs.insert_one.call_args[0][0]
    assert call_args["tenant_id"] == "tenant-1"
    assert call_args["status"] == "pending"


@pytest.mark.unit
async def test_update_document_status():
    """update_status updates document status and optional fields."""
    from src.services.ingestion.service import IngestionService

    mock_docs = MagicMock()
    mock_docs.update_one = AsyncMock()

    service = IngestionService(documents_collection=mock_docs, chunks_collection=MagicMock())
    await service.update_status("doc-123", "tenant-1", "processing")

    mock_docs.update_one.assert_called_once()
    filter_arg = mock_docs.update_one.call_args[0][0]
    assert filter_arg == {"_id": "doc-123", "tenant_id": "tenant-1"}


@pytest.mark.unit
async def test_check_duplicate_returns_existing():
    """check_duplicate returns existing doc_id when content_hash matches."""
    from src.services.ingestion.service import IngestionService

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(
        return_value={"_id": "existing-doc", "status": "ready"}
    )

    service = IngestionService(documents_collection=mock_docs, chunks_collection=MagicMock())
    result = await service.check_duplicate("tenant-1", "test.pdf", "abc123hash")

    assert result == "existing-doc"


@pytest.mark.unit
async def test_check_duplicate_returns_none_when_no_match():
    """check_duplicate returns None when no matching content_hash."""
    from src.services.ingestion.service import IngestionService

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=None)

    service = IngestionService(documents_collection=mock_docs, chunks_collection=MagicMock())
    result = await service.check_duplicate("tenant-1", "test.pdf", "abc123hash")

    assert result is None


@pytest.mark.unit
async def test_store_chunks_with_tenant_id_and_chunk_id():
    """store_chunks writes chunks with tenant_id, chunk_id, and embedding_model."""
    from src.services.ingestion.service import IngestionService
    from src.services.ingestion.chunker import DocumentChunk

    mock_chunks = MagicMock()
    mock_chunks.delete_many = AsyncMock()
    mock_chunks.insert_many = AsyncMock()

    service = IngestionService(documents_collection=MagicMock(), chunks_collection=mock_chunks)

    chunks = [
        DocumentChunk(
            content="test content",
            index=0,
            start_char=0,
            end_char=12,
            metadata={"heading_path": ["Section 1"], "content_type": "text"},
            token_count=3,
            embedding=[0.1] * 1536,
        )
    ]

    await service.store_chunks(
        chunks=chunks,
        document_id="doc-1",
        tenant_id="tenant-1",
        source="test.pdf",
        version=1,
        embedding_model="text-embedding-3-small",
    )

    # Old chunks deleted first
    mock_chunks.delete_many.assert_called_once()
    delete_filter = mock_chunks.delete_many.call_args[0][0]
    assert delete_filter["tenant_id"] == "tenant-1"
    assert delete_filter["document_id"] == "doc-1"

    # New chunks inserted
    mock_chunks.insert_many.assert_called_once()
    inserted = mock_chunks.insert_many.call_args[0][0]
    assert len(inserted) == 1
    assert inserted[0]["tenant_id"] == "tenant-1"
    assert "chunk_id" in inserted[0]
    assert inserted[0]["embedding_model"] == "text-embedding-3-small"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && uv run pytest tests/test_ingestion_service.py -v`
Expected: FAIL — `src.services.ingestion.service` module does not exist.

- [ ] **Step 3: Implement ingestion service**

Create `apps/api/src/services/ingestion/service.py`:

```python
"""Tenant-aware ingestion service for API and Celery use."""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from pymongo.asynchronous.collection import AsyncCollection

from src.models.document import ChunkModel, DocumentModel, DocumentStatus
from src.services.ingestion.chunker import DocumentChunk

logger = logging.getLogger(__name__)


class IngestionService:
    """Handles document and chunk persistence with tenant isolation."""

    def __init__(
        self,
        documents_collection: AsyncCollection,
        chunks_collection: AsyncCollection,
    ) -> None:
        self.documents = documents_collection
        self.chunks = chunks_collection

    async def create_pending_document(
        self,
        tenant_id: str,
        title: str,
        source: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Create a document record with pending status.

        Args:
            tenant_id: Tenant this document belongs to.
            title: Document title.
            source: Original filename or URI.
            metadata: Optional additional metadata.

        Returns:
            Inserted document ID as string.
        """
        now = datetime.now(timezone.utc)
        doc = {
            "tenant_id": tenant_id,
            "title": title,
            "source": source,
            "content": "",
            "content_hash": "",
            "version": 1,
            "status": DocumentStatus.PENDING,
            "chunk_count": 0,
            "metadata": metadata or {},
            "created_at": now,
            "updated_at": now,
        }
        result = await self.documents.insert_one(doc)
        return result.inserted_id

    async def update_status(
        self,
        document_id: str,
        tenant_id: str,
        status: str,
        error_message: Optional[str] = None,
        chunk_count: Optional[int] = None,
        content_hash: Optional[str] = None,
        version: Optional[int] = None,
        content: Optional[str] = None,
    ) -> None:
        """Update document processing status.

        Args:
            document_id: Document to update.
            tenant_id: Tenant ID for isolation.
            status: New status value.
            error_message: Error details if status is failed.
            chunk_count: Number of chunks created.
            content_hash: SHA256 hash of content.
            version: Document version.
            content: Full document content.
        """
        update: dict[str, Any] = {
            "$set": {
                "status": status,
                "updated_at": datetime.now(timezone.utc),
            }
        }
        if error_message is not None:
            update["$set"]["error_message"] = error_message
        if chunk_count is not None:
            update["$set"]["chunk_count"] = chunk_count
        if content_hash is not None:
            update["$set"]["content_hash"] = content_hash
        if version is not None:
            update["$set"]["version"] = version
        if content is not None:
            update["$set"]["content"] = content

        await self.documents.update_one(
            {"_id": document_id, "tenant_id": tenant_id},
            update,
        )

    async def check_duplicate(
        self,
        tenant_id: str,
        source: str,
        content_hash: str,
    ) -> Optional[str]:
        """Check if a document with the same content already exists.

        Args:
            tenant_id: Tenant to check within.
            source: Document source (filename or URI).
            content_hash: SHA256 hash of document content.

        Returns:
            Existing document ID if duplicate found, None otherwise.
        """
        existing = await self.documents.find_one(
            {
                "tenant_id": tenant_id,
                "source": source,
                "content_hash": content_hash,
                "status": DocumentStatus.READY,
            }
        )
        if existing:
            return existing["_id"]
        return None

    async def get_latest_version(
        self, tenant_id: str, source: str
    ) -> int:
        """Get the latest version number for a document source.

        Args:
            tenant_id: Tenant to check within.
            source: Document source.

        Returns:
            Latest version number, or 0 if no previous version exists.
        """
        doc = await self.documents.find_one(
            {"tenant_id": tenant_id, "source": source},
            sort=[("version", -1)],
        )
        if doc:
            return doc.get("version", 1)
        return 0

    async def store_chunks(
        self,
        chunks: list[DocumentChunk],
        document_id: str,
        tenant_id: str,
        source: str,
        version: int,
        embedding_model: str,
    ) -> int:
        """Delete old chunks and insert new ones with tenant isolation.

        Args:
            chunks: Document chunks with embeddings.
            document_id: Parent document ID.
            tenant_id: Tenant ID for isolation.
            source: Document source for chunk ID generation.
            version: Document version for chunk ID generation.
            embedding_model: Name of the embedding model used.

        Returns:
            Number of chunks inserted.
        """
        # Delete existing chunks for this document
        await self.chunks.delete_many(
            {"document_id": document_id, "tenant_id": tenant_id}
        )

        if not chunks:
            return 0

        chunk_dicts = []
        for chunk in chunks:
            chunk_id = ChunkModel.generate_chunk_id(
                source_uri=source,
                version=version,
                chunk_index=chunk.index,
                chunk_text=chunk.content,
            )

            heading_path = chunk.metadata.get("heading_path", [])
            if isinstance(heading_path, str):
                heading_path = [heading_path]

            content_type = chunk.metadata.get("content_type", "text")

            chunk_dicts.append(
                {
                    "tenant_id": tenant_id,
                    "document_id": document_id,
                    "chunk_id": chunk_id,
                    "content": chunk.content,
                    "embedding": chunk.embedding,
                    "chunk_index": chunk.index,
                    "heading_path": heading_path,
                    "content_type": content_type,
                    "embedding_model": embedding_model,
                    "token_count": chunk.token_count or 0,
                    "metadata": chunk.metadata,
                    "created_at": datetime.now(timezone.utc),
                }
            )

        await self.chunks.insert_many(chunk_dicts, ordered=False)
        logger.info(
            "Stored %d chunks for document %s (tenant: %s)",
            len(chunk_dicts),
            document_id,
            tenant_id,
        )
        return len(chunk_dicts)

    async def get_document_status(
        self, document_id: str, tenant_id: str
    ) -> Optional[dict[str, Any]]:
        """Get document status for polling endpoint.

        Args:
            document_id: Document to check.
            tenant_id: Tenant ID for isolation.

        Returns:
            Dict with status fields, or None if not found.
        """
        doc = await self.documents.find_one(
            {"_id": document_id, "tenant_id": tenant_id},
            projection={
                "_id": 1,
                "status": 1,
                "chunk_count": 1,
                "version": 1,
                "error_message": 1,
                "title": 1,
            },
        )
        return doc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/api && uv run pytest tests/test_ingestion_service.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/services/ingestion/service.py apps/api/tests/test_ingestion_service.py
git commit -m "feat: add tenant-aware ingestion service with tests"
```

---

## Task 8: Celery Worker

**Files:**
- Create: `apps/api/src/worker.py`

- [ ] **Step 1: Implement Celery worker with ingest_document task**

Create `apps/api/src/worker.py`:

```python
"""Celery worker configuration and tasks."""

import logging
import os
import tempfile

from celery import Celery
from celery.utils.log import get_task_logger

from src.core.settings import load_settings

settings = load_settings()

# Configure Celery
celery_app = Celery(
    "mongorag",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

task_logger = get_task_logger(__name__)


@celery_app.task(
    bind=True,
    name="mongorag.ingest_document",
    max_retries=3,
    autoretry_for=(ConnectionError, OSError),
    retry_backoff=10,
    retry_backoff_max=90,
)
def ingest_document(
    self,
    temp_path: str,
    document_id: str,
    tenant_id: str,
    title: str,
    source: str,
    metadata: dict | None = None,
) -> dict:
    """Process a document through the ingestion pipeline.

    This task runs synchronously inside the Celery worker. It uses
    asyncio.run() to execute the async pipeline methods.

    Args:
        temp_path: Path to the uploaded file in temp directory.
        document_id: MongoDB document ID (created by the endpoint).
        tenant_id: Tenant ID for isolation.
        title: Document title.
        source: Original filename.
        metadata: Optional metadata dict.

    Returns:
        Dict with document_id, status, chunk_count.
    """
    import asyncio

    async def _run() -> dict:
        from pymongo import AsyncMongoClient

        from src.models.document import DocumentModel, DocumentStatus
        from src.services.ingestion.chunker import ChunkingConfig, create_chunker
        from src.services.ingestion.embedder import create_embedder
        from src.services.ingestion.service import IngestionService

        client = AsyncMongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
        db = client[settings.mongodb_database]

        service = IngestionService(
            documents_collection=db[settings.mongodb_collection_documents],
            chunks_collection=db[settings.mongodb_collection_chunks],
        )

        try:
            # Update status to processing
            await service.update_status(document_id, tenant_id, DocumentStatus.PROCESSING)

            # Read and convert document
            from src.services.ingestion.ingest import DocumentIngestionPipeline, IngestionConfig

            config = IngestionConfig()
            pipeline = DocumentIngestionPipeline(config=config)
            content, docling_doc = pipeline._read_document(temp_path)

            if not content.strip():
                await service.update_status(
                    document_id, tenant_id, DocumentStatus.FAILED,
                    error_message="Document is empty or could not be parsed",
                )
                return {"document_id": document_id, "status": "failed", "chunk_count": 0}

            # Generate content hash
            content_hash = DocumentModel.hash_content(content)

            # Check for duplicate
            existing = await service.check_duplicate(tenant_id, source, content_hash)
            if existing:
                await service.update_status(
                    document_id, tenant_id, DocumentStatus.READY,
                    content_hash=content_hash,
                    content=content,
                )
                task_logger.info("Duplicate detected for %s, marking ready", document_id)
                return {"document_id": document_id, "status": "ready", "chunk_count": 0}

            # Determine version
            latest_version = await service.get_latest_version(tenant_id, source)
            version = latest_version + 1

            # Extract title if not provided
            if not title:
                title = pipeline._extract_title(content, temp_path)

            # Chunk document
            chunker = create_chunker(ChunkingConfig(max_tokens=config.max_tokens))
            chunks = await chunker.chunk_document(
                content=content,
                title=title,
                source=source,
                metadata=metadata or {},
                docling_doc=docling_doc,
            )

            if not chunks:
                await service.update_status(
                    document_id, tenant_id, DocumentStatus.FAILED,
                    error_message="No chunks created from document",
                )
                return {"document_id": document_id, "status": "failed", "chunk_count": 0}

            # Embed chunks
            embedder = create_embedder()
            embedded_chunks = await embedder.embed_chunks(chunks)

            # Store chunks with tenant isolation
            chunk_count = await service.store_chunks(
                chunks=embedded_chunks,
                document_id=document_id,
                tenant_id=tenant_id,
                source=source,
                version=version,
                embedding_model=settings.embedding_model,
            )

            # Update document to ready
            await service.update_status(
                document_id, tenant_id, DocumentStatus.READY,
                chunk_count=chunk_count,
                content_hash=content_hash,
                version=version,
                content=content,
            )

            task_logger.info(
                "Ingestion complete: doc=%s, tenant=%s, chunks=%d",
                document_id, tenant_id, chunk_count,
            )

            return {
                "document_id": document_id,
                "status": "ready",
                "chunk_count": chunk_count,
            }

        except Exception as e:
            task_logger.exception("Ingestion failed: doc=%s, error=%s", document_id, str(e))
            try:
                await service.update_status(
                    document_id, tenant_id, DocumentStatus.FAILED,
                    error_message=str(e),
                )
            except Exception:
                task_logger.exception("Failed to update status after error")
            raise  # Let Celery retry if applicable

        finally:
            await client.close()
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
                task_logger.info("Cleaned up temp file: %s", temp_path)

    return asyncio.run(_run())
```

- [ ] **Step 2: Commit**

```bash
git add apps/api/src/worker.py
git commit -m "feat: add Celery worker with ingest_document task"
```

---

## Task 9: Ingestion Router

**Files:**
- Create: `apps/api/src/routers/ingest.py`
- Create: `apps/api/tests/test_ingest_router.py`

- [ ] **Step 1: Write failing tests for ingestion endpoints**

Create `apps/api/tests/test_ingest_router.py`:

```python
"""Tests for ingestion router."""

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from tests.conftest import MOCK_TENANT_ID


@pytest.fixture
def app_client():
    """Create test client with mocked Celery and MongoDB."""
    with patch("src.main._deps") as mock_deps:
        mock_deps.initialize = AsyncMock()
        mock_deps.cleanup = AsyncMock()
        mock_deps.db = MagicMock()
        mock_deps.settings = MagicMock()
        mock_deps.settings.max_upload_size_mb = 50
        mock_deps.settings.upload_temp_dir = "/tmp/test-uploads"
        mock_deps.documents_collection = MagicMock()
        mock_deps.documents_collection.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id="doc-test-123")
        )
        mock_deps.documents_collection.find_one = AsyncMock(return_value=None)

        from src.main import app
        with TestClient(app) as c:
            yield c, mock_deps


@pytest.mark.unit
def test_ingest_missing_tenant_header(app_client):
    """Ingest without X-Tenant-ID returns 400."""
    client, _ = app_client
    file = io.BytesIO(b"test content")
    response = client.post(
        "/api/v1/documents/ingest",
        files={"file": ("test.txt", file, "text/plain")},
    )
    assert response.status_code == 400


@pytest.mark.unit
def test_ingest_unsupported_format(app_client):
    """Ingest with unsupported file format returns 422."""
    client, _ = app_client
    file = io.BytesIO(b"test content")
    response = client.post(
        "/api/v1/documents/ingest",
        files={"file": ("test.exe", file, "application/octet-stream")},
        headers={"X-Tenant-ID": MOCK_TENANT_ID},
    )
    assert response.status_code == 422


@pytest.mark.unit
def test_ingest_valid_file_returns_202(app_client):
    """Ingest with valid file returns 202 Accepted."""
    client, mock_deps = app_client

    with patch("src.routers.ingest.ingest_document") as mock_task, \
         patch("src.routers.ingest.IngestionService") as mock_service_cls, \
         patch("os.makedirs"), \
         patch("builtins.open", create=True), \
         patch("shutil.copyfileobj"):

        mock_task.delay.return_value = MagicMock(id="celery-task-123")

        mock_service = MagicMock()
        mock_service.create_pending_document = AsyncMock(return_value="doc-test-123")
        mock_service_cls.return_value = mock_service

        file = io.BytesIO(b"# Test Document\n\nSome content here.")
        response = client.post(
            "/api/v1/documents/ingest",
            files={"file": ("test.md", file, "text/markdown")},
            headers={"X-Tenant-ID": MOCK_TENANT_ID},
        )

        assert response.status_code == 202
        data = response.json()
        assert data["document_id"] == "doc-test-123"
        assert data["status"] == "pending"
        assert "task_id" in data


@pytest.mark.unit
def test_document_status_returns_status(app_client):
    """GET document status returns current document status."""
    client, mock_deps = app_client

    with patch("src.routers.ingest.IngestionService") as mock_service_cls:
        mock_service = MagicMock()
        mock_service.get_document_status = AsyncMock(return_value={
            "_id": "doc-123",
            "status": "ready",
            "chunk_count": 42,
            "version": 1,
            "title": "Test Doc",
        })
        mock_service_cls.return_value = mock_service

        response = client.get(
            "/api/v1/documents/doc-123/status",
            headers={"X-Tenant-ID": MOCK_TENANT_ID},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["chunk_count"] == 42


@pytest.mark.unit
def test_document_status_not_found(app_client):
    """GET document status for nonexistent document returns 404."""
    client, mock_deps = app_client

    with patch("src.routers.ingest.IngestionService") as mock_service_cls:
        mock_service = MagicMock()
        mock_service.get_document_status = AsyncMock(return_value=None)
        mock_service_cls.return_value = mock_service

        response = client.get(
            "/api/v1/documents/nonexistent/status",
            headers={"X-Tenant-ID": MOCK_TENANT_ID},
        )

        assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && uv run pytest tests/test_ingest_router.py -v`
Expected: FAIL — `src.routers.ingest` module does not exist.

- [ ] **Step 3: Implement ingestion router**

Create `apps/api/src/routers/ingest.py`:

```python
"""Document ingestion endpoints."""

import logging
import os
import shutil
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from src.core.settings import Settings, load_settings
from src.core.tenant import get_tenant_id
from src.models.api import DocumentStatusResponse, IngestResponse
from src.services.ingestion.service import IngestionService
from src.worker import ingest_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

SUPPORTED_EXTENSIONS = {
    ".pdf", ".txt", ".md", ".markdown", ".docx", ".doc",
    ".pptx", ".ppt", ".xlsx", ".xls", ".html", ".htm",
}


def _get_settings() -> Settings:
    return load_settings()


def _validate_file(file: UploadFile, settings: Settings) -> str:
    """Validate uploaded file format and size.

    Args:
        file: Uploaded file.
        settings: App settings for size limits.

    Returns:
        File extension string.

    Raises:
        HTTPException: 422 for unsupported format, 413 for oversized file.
    """
    filename = file.filename or "unknown"
    ext = os.path.splitext(filename)[1].lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file format: {ext}. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    # Check content length if available
    if file.size and file.size > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {settings.max_upload_size_mb}MB",
        )

    return ext


@router.post("/ingest", response_model=IngestResponse, status_code=202)
async def ingest_document_endpoint(
    file: UploadFile = File(...),
    title: Optional[str] = Form(default=None),
    metadata: Optional[str] = Form(default=None),
    tenant_id: str = Depends(get_tenant_id),
    settings: Settings = Depends(_get_settings),
) -> IngestResponse:
    """Upload and ingest a document.

    Validates the file, creates a pending document record, saves the file
    to a temp directory, and dispatches a Celery task for processing.

    Returns 202 Accepted immediately with document_id and task_id.
    """
    ext = _validate_file(file, settings)
    source = file.filename or f"upload-{uuid.uuid4()}{ext}"

    # Parse metadata JSON if provided
    import json
    meta = {}
    if metadata:
        try:
            meta = json.loads(metadata)
        except json.JSONDecodeError:
            raise HTTPException(status_code=422, detail="Invalid metadata JSON")

    # Get deps from app state
    from src.main import _deps

    service = IngestionService(
        documents_collection=_deps.documents_collection,
        chunks_collection=_deps.chunks_collection,
    )

    # Create pending document
    document_id = await service.create_pending_document(
        tenant_id=tenant_id,
        title=title or os.path.splitext(source)[0],
        source=source,
        metadata=meta,
    )

    # Save file to temp directory
    temp_dir = os.path.join(settings.upload_temp_dir, str(uuid.uuid4()))
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, source)

    with open(temp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Dispatch Celery task
    task = ingest_document.delay(
        temp_path=temp_path,
        document_id=str(document_id),
        tenant_id=tenant_id,
        title=title or os.path.splitext(source)[0],
        source=source,
        metadata=meta,
    )

    logger.info(
        "Ingestion dispatched: doc=%s, tenant=%s, task=%s",
        document_id, tenant_id, task.id,
    )

    return IngestResponse(
        document_id=str(document_id),
        status="pending",
        task_id=task.id,
    )


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: str,
    tenant_id: str = Depends(get_tenant_id),
) -> DocumentStatusResponse:
    """Get document processing status.

    Returns current status, chunk count, and version for the given document.
    Returns 404 if document not found or belongs to a different tenant.
    """
    from src.main import _deps

    service = IngestionService(
        documents_collection=_deps.documents_collection,
        chunks_collection=_deps.chunks_collection,
    )

    doc = await service.get_document_status(document_id, tenant_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentStatusResponse(
        document_id=str(doc["_id"]),
        status=doc.get("status", "unknown"),
        chunk_count=doc.get("chunk_count", 0),
        version=doc.get("version", 1),
        error_message=doc.get("error_message"),
    )
```

- [ ] **Step 4: Register ingest router in main.py**

In `apps/api/src/main.py`, add the import and include the router:

Add after the existing health import:
```python
from src.routers.ingest import router as ingest_router
```

Add after the existing `app.include_router(health_router)`:
```python
app.include_router(ingest_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd apps/api && uv run pytest tests/test_ingest_router.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/routers/ingest.py apps/api/tests/test_ingest_router.py apps/api/src/main.py
git commit -m "feat: add document ingestion endpoint with Celery dispatch"
```

---

## Task 10: Chat Service (Shared Orchestration)

**Files:**
- Create: `apps/api/src/services/chat.py`

- [ ] **Step 1: Implement shared chat service**

Create `apps/api/src/services/chat.py`:

```python
"""Chat orchestration service shared by REST and WebSocket transports."""

import logging
from typing import Any, AsyncIterator, Optional

from src.core.dependencies import AgentDependencies
from src.models.api import SourceReference
from src.models.conversation import ChatMessage, MessageRole
from src.services.agent import create_rag_agent, format_search_context, run_search
from src.services.conversation import ConversationService

logger = logging.getLogger(__name__)


class ChatService:
    """Orchestrates the RAG chat flow: search, prompt, LLM, persistence."""

    def __init__(self, deps: AgentDependencies) -> None:
        self.deps = deps
        self.conversation_service = ConversationService(deps.conversations_collection)

    async def handle_message(
        self,
        message: str,
        tenant_id: str,
        conversation_id: Optional[str] = None,
        search_type: str = "hybrid",
    ) -> dict[str, Any]:
        """Handle a chat message and return the full response (non-streaming).

        Args:
            message: User's message text.
            tenant_id: Tenant ID for isolation.
            conversation_id: Existing conversation ID, or None for new.
            search_type: Search type to use.

        Returns:
            Dict with answer, sources, conversation_id.

        Raises:
            ValueError: If conversation_id belongs to a different tenant.
        """
        # Get or create conversation
        conv = await self.conversation_service.get_or_create(tenant_id, conversation_id)
        if conv is None:
            raise ValueError("Conversation not found")

        conv_id = str(conv["_id"])

        # Persist user message
        user_msg = ChatMessage(role=MessageRole.USER, content=message)
        await self.conversation_service.append_message(conv_id, tenant_id, user_msg)

        # Run search
        results = await run_search(
            self.deps, message, tenant_id, search_type=search_type
        )

        # Build context
        context = format_search_context(results)

        # Get conversation history for multi-turn
        history = await self.conversation_service.get_history(conv_id, tenant_id, limit=10)

        # Build messages for LLM
        history_text = ""
        if history and len(history) > 1:
            history_parts = []
            for msg in history[:-1]:  # Exclude the just-added user message
                role = msg.get("role", "user")
                content = msg.get("content", "")
                history_parts.append(f"{role}: {content}")
            history_text = "\n".join(history_parts)

        user_prompt = message
        if context and context != "No relevant documents found in the knowledge base.":
            user_prompt = f"Context from knowledge base:\n\n{context}\n\nUser question: {message}"
        if history_text:
            user_prompt = f"Conversation history:\n{history_text}\n\n{user_prompt}"

        # Call LLM
        agent = create_rag_agent()
        result = await agent.run(user_prompt)

        answer = result.output if hasattr(result, 'output') else str(result.data)

        # Extract sources
        sources = [
            SourceReference(
                document_title=r.document_title,
                heading_path=r.metadata.get("heading_path", []),
                snippet=r.content[:200],
            )
            for r in results[:5]
        ]

        # Persist assistant message
        assistant_msg = ChatMessage(
            role=MessageRole.ASSISTANT,
            content=answer,
            sources=[s.document_title for s in sources],
        )
        await self.conversation_service.append_message(conv_id, tenant_id, assistant_msg)

        return {
            "answer": answer,
            "sources": sources,
            "conversation_id": conv_id,
        }

    async def handle_message_stream(
        self,
        message: str,
        tenant_id: str,
        conversation_id: Optional[str] = None,
        search_type: str = "hybrid",
    ) -> AsyncIterator[dict[str, Any]]:
        """Handle a chat message with streaming token output.

        Yields dicts with type: token|sources|done|error.

        Args:
            message: User's message text.
            tenant_id: Tenant ID for isolation.
            conversation_id: Existing conversation ID, or None for new.
            search_type: Search type to use.

        Yields:
            Event dicts: {"type": "token", "content": "..."} etc.
        """
        # Get or create conversation
        conv = await self.conversation_service.get_or_create(tenant_id, conversation_id)
        if conv is None:
            yield {"type": "error", "message": "Conversation not found"}
            return

        conv_id = str(conv["_id"])

        # Persist user message
        user_msg = ChatMessage(role=MessageRole.USER, content=message)
        await self.conversation_service.append_message(conv_id, tenant_id, user_msg)

        # Run search
        results = await run_search(
            self.deps, message, tenant_id, search_type=search_type
        )

        # Build context
        context = format_search_context(results)

        # Get conversation history
        history = await self.conversation_service.get_history(conv_id, tenant_id, limit=10)

        history_text = ""
        if history and len(history) > 1:
            history_parts = []
            for msg in history[:-1]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                history_parts.append(f"{role}: {content}")
            history_text = "\n".join(history_parts)

        user_prompt = message
        if context and context != "No relevant documents found in the knowledge base.":
            user_prompt = f"Context from knowledge base:\n\n{context}\n\nUser question: {message}"
        if history_text:
            user_prompt = f"Conversation history:\n{history_text}\n\n{user_prompt}"

        # Stream LLM response
        agent = create_rag_agent()
        full_answer = ""

        try:
            async with agent.run_stream(user_prompt) as stream:
                async for text in stream.stream_text(delta=True):
                    full_answer += text
                    yield {"type": "token", "content": text}
        except Exception as e:
            logger.exception("LLM streaming error: %s", str(e))
            yield {"type": "error", "message": f"LLM error: {str(e)}"}
            return

        # Send sources
        sources = [
            SourceReference(
                document_title=r.document_title,
                heading_path=r.metadata.get("heading_path", []),
                snippet=r.content[:200],
            )
            for r in results[:5]
        ]
        yield {
            "type": "sources",
            "sources": [s.model_dump() for s in sources],
        }

        # Persist assistant message
        assistant_msg = ChatMessage(
            role=MessageRole.ASSISTANT,
            content=full_answer,
            sources=[s.document_title for s in sources],
        )
        await self.conversation_service.append_message(conv_id, tenant_id, assistant_msg)

        yield {"type": "done", "conversation_id": conv_id}
```

- [ ] **Step 2: Commit**

```bash
git add apps/api/src/services/chat.py
git commit -m "feat: add shared chat orchestration service with streaming support"
```

---

## Task 11: Chat Router (REST + SSE + WebSocket)

**Files:**
- Create: `apps/api/src/routers/chat.py`
- Create: `apps/api/tests/test_chat_router.py`

- [ ] **Step 1: Write failing tests for chat endpoints**

Create `apps/api/tests/test_chat_router.py`:

```python
"""Tests for chat router."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from tests.conftest import MOCK_TENANT_ID


@pytest.fixture
def app_client():
    """Create test client with mocked deps."""
    with patch("src.main._deps") as mock_deps:
        mock_deps.initialize = AsyncMock()
        mock_deps.cleanup = AsyncMock()
        mock_deps.db = MagicMock()
        mock_deps.settings = MagicMock()
        mock_deps.conversations_collection = MagicMock()

        from src.main import app
        with TestClient(app) as c:
            yield c, mock_deps


@pytest.mark.unit
def test_chat_missing_tenant_header(app_client):
    """Chat without X-Tenant-ID returns 400."""
    client, _ = app_client
    response = client.post(
        "/api/v1/chat",
        json={"message": "Hello"},
    )
    assert response.status_code == 400


@pytest.mark.unit
def test_chat_empty_message(app_client):
    """Chat with empty message returns 422."""
    client, _ = app_client
    response = client.post(
        "/api/v1/chat",
        json={"message": ""},
        headers={"X-Tenant-ID": MOCK_TENANT_ID},
    )
    assert response.status_code == 422


@pytest.mark.unit
def test_chat_valid_request_returns_response(app_client):
    """Chat with valid request returns answer and conversation_id."""
    client, mock_deps = app_client

    mock_result = {
        "answer": "Here is the answer.",
        "sources": [],
        "conversation_id": "conv-123",
    }

    with patch("src.routers.chat.ChatService") as mock_chat_cls:
        mock_chat = MagicMock()
        mock_chat.handle_message = AsyncMock(return_value=mock_result)
        mock_chat_cls.return_value = mock_chat

        response = client.post(
            "/api/v1/chat",
            json={"message": "How do I configure SSO?"},
            headers={"X-Tenant-ID": MOCK_TENANT_ID},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Here is the answer."
        assert data["conversation_id"] == "conv-123"


@pytest.mark.unit
def test_chat_conversation_not_found(app_client):
    """Chat with nonexistent conversation_id returns 404."""
    client, mock_deps = app_client

    with patch("src.routers.chat.ChatService") as mock_chat_cls:
        mock_chat = MagicMock()
        mock_chat.handle_message = AsyncMock(side_effect=ValueError("Conversation not found"))
        mock_chat_cls.return_value = mock_chat

        response = client.post(
            "/api/v1/chat",
            json={"message": "Hello", "conversation_id": "nonexistent"},
            headers={"X-Tenant-ID": MOCK_TENANT_ID},
        )

        assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && uv run pytest tests/test_chat_router.py -v`
Expected: FAIL — `src.routers.chat` module does not exist.

- [ ] **Step 3: Implement chat router**

Create `apps/api/src/routers/chat.py`:

```python
"""Chat endpoints: REST (JSON + SSE) and WebSocket."""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from src.core.tenant import get_tenant_id
from src.models.api import ChatRequest, ChatResponse, WSMessage
from src.services.chat import ChatService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])


def _get_chat_service() -> ChatService:
    """Get ChatService with app-level deps."""
    from src.main import _deps
    return ChatService(_deps)


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    body: ChatRequest,
    request: Request,
    tenant_id: str = Depends(get_tenant_id),
) -> ChatResponse | StreamingResponse:
    """Handle a chat message.

    If Accept header includes text/event-stream, streams tokens via SSE.
    Otherwise returns the full response as JSON.
    """
    accept = request.headers.get("accept", "")
    service = _get_chat_service()

    # SSE streaming path
    if "text/event-stream" in accept:
        async def event_generator():
            async for event in service.handle_message_stream(
                message=body.message,
                tenant_id=tenant_id,
                conversation_id=body.conversation_id,
                search_type=body.search_type,
            ):
                yield f"data: {json.dumps(event)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Non-streaming JSON path
    try:
        result = await service.handle_message(
            message=body.message,
            tenant_id=tenant_id,
            conversation_id=body.conversation_id,
            search_type=body.search_type,
        )
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    return ChatResponse(
        answer=result["answer"],
        sources=result["sources"],
        conversation_id=result["conversation_id"],
    )


@router.websocket("/chat/ws")
async def chat_websocket(
    websocket: WebSocket,
    tenant_id: Optional[str] = None,
):
    """WebSocket endpoint for real-time chat.

    Tenant ID is passed as query parameter: /api/v1/chat/ws?tenant_id=...
    """
    if not tenant_id:
        await websocket.close(code=4001, reason="tenant_id query parameter required")
        return

    await websocket.accept()
    service = _get_chat_service()

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                data = json.loads(raw)
                msg = WSMessage(**data)
            except (json.JSONDecodeError, Exception) as e:
                await websocket.send_json(
                    {"type": "error", "message": f"Invalid message format: {str(e)}"}
                )
                continue

            if msg.type == "cancel":
                # Cancel is a no-op for now (future: cancel in-flight LLM calls)
                await websocket.send_json({"type": "cancelled"})
                continue

            if msg.type == "message" and msg.content:
                try:
                    async for event in service.handle_message_stream(
                        message=msg.content,
                        tenant_id=tenant_id,
                        conversation_id=msg.conversation_id,
                    ):
                        await websocket.send_json(event)
                except Exception as e:
                    logger.exception("WebSocket chat error: %s", str(e))
                    await websocket.send_json(
                        {"type": "error", "message": f"Chat error: {str(e)}"}
                    )
            else:
                await websocket.send_json(
                    {"type": "error", "message": "Expected type 'message' with content"}
                )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: tenant=%s", tenant_id)
    except Exception as e:
        logger.exception("WebSocket error: %s", str(e))
        try:
            await websocket.close(code=1011, reason="Internal error")
        except Exception:
            pass
```

- [ ] **Step 4: Register chat router in main.py**

In `apps/api/src/main.py`, add the import and include:

Add after the ingest import:
```python
from src.routers.chat import router as chat_router
```

Add after `app.include_router(ingest_router)`:
```python
app.include_router(chat_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd apps/api && uv run pytest tests/test_chat_router.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/routers/chat.py apps/api/tests/test_chat_router.py apps/api/src/main.py
git commit -m "feat: add chat endpoint with REST, SSE, and WebSocket support"
```

---

## Task 12: Final Wiring & Lint

**Files:**
- Modify: `apps/api/src/main.py` (verify all routers registered)
- All files

- [ ] **Step 1: Verify main.py has all routers**

Read `apps/api/src/main.py` and confirm it includes:
- `health_router`
- `ingest_router`
- `chat_router`

The final `main.py` should look like:

```python
"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.dependencies import AgentDependencies
from src.routers.chat import router as chat_router
from src.routers.health import router as health_router
from src.routers.ingest import router as ingest_router

logger = logging.getLogger(__name__)

# Shared dependencies instance for app lifecycle
_deps = AgentDependencies()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and clean up application resources."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger.info("Starting MongoRAG API...")
    try:
        await _deps.initialize()
        logger.info("MongoRAG API started successfully")
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
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
app.include_router(ingest_router)
app.include_router(chat_router)
```

- [ ] **Step 2: Run linter**

Run: `cd apps/api && uv run ruff check . --fix`
Expected: No errors (or auto-fixed).

Run: `cd apps/api && uv run ruff format .`
Expected: Files formatted.

- [ ] **Step 3: Run all tests**

Run: `cd apps/api && uv run pytest tests/ -v`
Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: final wiring, lint fixes, all tests passing"
```

---

## Task Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Dependencies & configuration | pyproject.toml, .env.example, settings.py |
| 2 | Document status & API models | document.py, api.py |
| 3 | Tenant dependency | tenant.py, test_tenant.py, conftest.py |
| 4 | Tenant-filtered search | search.py, test_search_tenant.py |
| 5 | Agent refactor | agent.py, prompts.py |
| 6 | Conversation service | conversation.py, test_conversation.py |
| 7 | Ingestion service | ingestion/service.py, test_ingestion_service.py |
| 8 | Celery worker | worker.py |
| 9 | Ingestion router | routers/ingest.py, test_ingest_router.py, main.py |
| 10 | Chat service | services/chat.py |
| 11 | Chat router | routers/chat.py, test_chat_router.py, main.py |
| 12 | Final wiring & lint | main.py, all files |
