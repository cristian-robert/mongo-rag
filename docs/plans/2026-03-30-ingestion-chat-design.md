# Ingestion Pipeline & RAG Chat Design

**Issues:** #5 (Document Ingestion Pipeline), #6 (RAG Retrieval & Chat Endpoint)
**Date:** 2026-03-30
**Status:** Approved

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Background processing | Celery + Redis | User has Redis account; proper task queue from day one |
| Streaming transport | WebSocket (widget) + SSE (REST API) | WebSocket for persistent widget connections, SSE for programmatic API access |
| Model tiering | Skip — single configured model | Need production data to calibrate escalation thresholds |
| Auth stub | `X-Tenant-ID` header | Enforces tenant isolation now; real auth (Phase 3) swaps in via same dependency |
| File upload | Multipart form upload | Simple, no cloud storage dependency, 50MB limit |

## Architecture

```
┌─────────────┐    ┌──────────────────────────────────────────────────┐
│   Client     │    │  FastAPI (apps/api)                              │
│  (widget /   │───>│                                                  │
│   curl /     │    │  POST /api/v1/documents/ingest  --> Celery task  │
│   dashboard) │    │  POST /api/v1/chat              --> SSE stream   │
│              │<-->│  WS   /api/v1/chat/ws           --> WebSocket    │
│              │    │  GET  /api/v1/documents/{id}/status              │
│              │    │                                                  │
│              │    │  Middleware: X-Tenant-ID -> tenant_id dependency  │
└─────────────┘    └────────┬──────────────┬──────────────┬───────────┘
                            │              │              │
                     ┌──────▼──────┐ ┌─────▼─────┐ ┌─────▼─────┐
                     │  MongoDB    │ │  Redis     │ │  OpenAI   │
                     │  Atlas      │ │  (broker)  │ │  Embeddings│
                     │  - documents│ │  - tasks   │ │  & LLM    │
                     │  - chunks   │ │  - results │ └───────────┘
                     │  - convos   │ └───────────┘
                     └─────────────┘
```

### New Files

| File | Purpose |
|------|---------|
| `src/routers/ingest.py` | Ingestion endpoint |
| `src/routers/chat.py` | Chat endpoint (REST + SSE + WebSocket) |
| `src/worker.py` | Celery app + ingestion task |
| `src/core/tenant.py` | `X-Tenant-ID` extraction dependency |
| `src/services/conversation.py` | Conversation CRUD service |

### Modified Files

| File | Changes |
|------|---------|
| `src/services/ingestion/ingest.py` | Add tenant_id, content_hash, stable chunk IDs, version tracking |
| `src/services/search.py` | Add tenant_id filter to all search pipelines |
| `src/services/agent.py` | Accept deps via FastAPI DI, pass tenant_id to search |
| `src/core/prompts.py` | Versioned templates with tenant customization |
| `src/main.py` | Register new routers |
| `pyproject.toml` | Add celery, redis dependencies |

## Ingestion Pipeline (Issue #5)

### Endpoint

```
POST /api/v1/documents/ingest
Content-Type: multipart/form-data
X-Tenant-ID: tenant-uuid

Body:
  - file: UploadFile (PDF, TXT, MD, DOCX, PPTX, XLSX, HTML) — max 50MB
  - title: Optional[str]
  - metadata: Optional[JSON string]

Response (202 Accepted):
  { "document_id": "abc123", "status": "pending", "task_id": "celery-uuid" }
```

### Flow

1. Endpoint validates file (size, format) and saves to temp dir
2. Creates document record in MongoDB (status: "pending")
3. Dispatches Celery task with (temp_path, document_id, tenant_id)
4. Returns 202 immediately

Celery worker picks up task:

5. Updates document status to "processing"
6. Reads file via Docling (converts to markdown)
7. Chunks via HybridChunker (extracts heading_path, content_type)
8. Generates content_hash (SHA256 of full content)
9. Checks for existing doc with same (tenant_id, source, content_hash):
   - Same hash: no-op, mark "ready"
   - Different hash: bump version, delete old chunks, continue
10. Generates stable chunk_ids: `SHA256(source + version + index + text_hash)`
11. Batch embeds via OpenAI
12. Stores chunks with tenant_id, document_id, embedding_model, heading_path
13. Updates document status to "ready" (or "failed" with error)

### Status Polling

```
GET /api/v1/documents/{document_id}/status
X-Tenant-ID: tenant-uuid

Response:
  { "document_id": "abc123", "status": "ready", "chunk_count": 42, "version": 1 }
```

### Idempotency

Re-ingesting the same file with identical content is a no-op (content_hash match). Changed content triggers version bump: old chunks deleted, new chunks inserted with incremented version.

## RAG Chat (Issue #6)

### REST Endpoint

```
POST /api/v1/chat
X-Tenant-ID: tenant-uuid

Request:
  {
    "message": "How do I configure SSO?",
    "conversation_id": "optional-existing-id",
    "search_type": "hybrid"
  }

Response (Accept: application/json):
  {
    "answer": "To configure SSO, ...",
    "sources": [
      { "document_title": "Admin Guide", "heading_path": ["Auth", "SSO"], "snippet": "..." }
    ],
    "conversation_id": "conv-uuid"
  }

Response (Accept: text/event-stream):
  data: {"type": "token", "content": "To"}
  data: {"type": "token", "content": " configure"}
  ...
  data: {"type": "sources", "sources": [...]}
  data: {"type": "done", "conversation_id": "conv-uuid"}
```

### WebSocket Endpoint

```
WS /api/v1/chat/ws
Query param: tenant_id=...

Client -> Server:
  { "type": "message", "content": "How do I...", "conversation_id": "..." }
  { "type": "cancel" }

Server -> Client:
  { "type": "token", "content": "To" }
  { "type": "sources", "sources": [...] }
  { "type": "done", "conversation_id": "conv-uuid" }
  { "type": "error", "message": "..." }
```

### Shared Chat Flow

1. Extract tenant_id (header for REST, query param for WS)
2. Load or create conversation (MongoDB conversations collection)
3. Append user message to conversation
4. Embed user query
5. Hybrid search filtered by tenant_id:
   - `$vectorSearch` adds `filter: { "tenant_id": tenant_id }`
   - `$search` uses compound query with tenant_id filter
6. Build prompt: system template + retrieved context + conversation history (last 10 messages)
7. Call LLM via Pydantic AI `agent.run_stream()`
8. Stream tokens to client (SSE events or WS frames)
9. On completion: extract source citations, append assistant message to conversation
10. Return/send sources + conversation_id

### Tenant Filtering in Search

Vector search adds filter to `$vectorSearch` stage:
```python
"filter": { "tenant_id": tenant_id }
```

Text search wraps in compound query:
```python
"$search": {
    "index": "text_index",
    "compound": {
        "must": [{"text": {"query": query, "path": "content", "fuzzy": ...}}],
        "filter": [{"equals": {"path": "tenant_id", "value": tenant_id}}]
    }
}
```

### Conversation Service

- `get_or_create(tenant_id, conversation_id) -> ConversationModel`
- `append_message(conversation_id, message) -> None`
- `get_history(conversation_id, limit=10) -> list[ChatMessage]`

### Agent Refactor

- Replace self-created `AgentDependencies` in tool with deps passed from FastAPI lifespan
- Search tools receive `tenant_id` as parameter
- System prompt becomes template: `SYSTEM_PROMPT_V1.format(product_name=...)`

## Celery + Redis Setup

### Configuration

New env var: `REDIS_URL=redis://...`

`src/worker.py`:
- Celery app with Redis as broker and result backend
- Single task: `ingest_document(temp_path, document_id, tenant_id, config)`
- Uses existing `DocumentIngestionPipeline` methods internally

### Running

```bash
cd apps/api
uv run celery -A src.worker worker --loglevel=info --concurrency=2
```

### Task Lifecycle

```
PENDING -> PROCESSING -> READY
                     \-> FAILED (error stored on document)
```

Status stored on the `documents` collection directly. Celery result backend is for Celery internals only.

### Retry Policy

3 retries with exponential backoff (10s, 30s, 90s) for transient failures (embedding API timeouts, MongoDB connection drops). Docling parse errors are not retried.

## Error Handling & Validation

### Ingestion

- File size > 50MB: 413
- Unsupported format: 422
- Tenant not found: 404
- Duplicate (same tenant_id + source + content_hash, status "ready"): return existing document_id with 200

### Chat

- Empty/missing message: 422
- Message > 10,000 chars: 422
- conversation_id belongs to different tenant: 404 (not 403, avoids leaking existence)
- No documents for tenant: graceful response ("I don't have any documents to search yet")

### WebSocket

- Invalid tenant_id on connect: close with code 4001
- Malformed message: send error event, keep connection open
- LLM/search failure mid-stream: send error event, close gracefully
- Connection drop: conversation state already persisted, client reconnects via conversation_id

### Celery Task Failures

- Embedding API error: retry (3x exponential backoff)
- Docling parse error: mark "failed", no retry
- MongoDB write error: retry
- All retries exhausted: mark "failed", log for alerting
