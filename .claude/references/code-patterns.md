# MongoRAG Code Patterns & Conventions

> **Loading trigger:** Read this file when writing, reviewing, or debugging backend or frontend code.

---

## Backend Patterns (FastAPI + Python)

### FastAPI Endpoint Structure

```python
from fastapi import APIRouter, Depends, HTTPException, status
from src.dependencies import get_db, get_current_tenant
from src.models import DocumentCreate, DocumentResponse

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

@router.post("/", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    doc: DocumentCreate,
    db=Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
):
    result = await db.documents.insert_one({
        **doc.model_dump(),
        "tenant_id": tenant_id,
    })
    return {**doc.model_dump(), "id": str(result.inserted_id), "tenant_id": tenant_id}
```

### Pydantic Models for Request/Response

```python
from pydantic import BaseModel, Field
from datetime import datetime

class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    source: str
    content: str

class DocumentResponse(BaseModel):
    id: str
    title: str
    source: str
    tenant_id: str
    created_at: datetime

    model_config = {"from_attributes": True}
```

### Pydantic Settings Configuration

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    mongodb_uri: str
    llm_api_key: str
    embedding_api_key: str
    llm_model: str = "anthropic/claude-haiku-4.5"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
```

### Dependency Injection (Tenant Isolation)

```python
from fastapi import Depends, Header, HTTPException

async def get_current_tenant(x_api_key: str = Header(...)) -> str:
    """Extract tenant_id from API key. EVERY query must use this."""
    api_key_doc = await db.api_keys.find_one({"key_hash": hash_key(x_api_key)})
    if not api_key_doc:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key_doc["tenant_id"]
```

### Hybrid RRF Search (from reference repo)

```python
import asyncio

async def hybrid_search(query: str, tenant_id: str, limit: int = 5):
    embedding = await get_embedding(query)

    # Run both searches concurrently
    vector_results, text_results = await asyncio.gather(
        vector_search(embedding, tenant_id, limit),
        text_search(query, tenant_id, limit),
    )

    # Reciprocal Rank Fusion
    scores: dict[str, float] = {}
    for rank, doc in enumerate(vector_results):
        scores[doc["_id"]] = scores.get(doc["_id"], 0) + 1 / (60 + rank)
    for rank, doc in enumerate(text_results):
        scores[doc["_id"]] = scores.get(doc["_id"], 0) + 1 / (60 + rank)

    # Sort by RRF score, return top results
    sorted_ids = sorted(scores, key=scores.get, reverse=True)[:limit]
    return [doc for doc in vector_results + text_results if doc["_id"] in sorted_ids]
```

### MongoDB Vector Search Aggregation

```python
async def vector_search(embedding: list[float], tenant_id: str, limit: int):
    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": embedding,
                "numCandidates": limit * 10,
                "limit": limit,
                "filter": {"tenant_id": tenant_id},
            }
        },
        {"$project": {"content": 1, "document_id": 1, "score": {"$meta": "vectorSearchScore"}}},
    ]
    return await db.chunks.aggregate(pipeline).to_list(length=limit)
```

---

## Frontend Patterns (Next.js)

### Server Component (default)

```typescript
// app/(dashboard)/documents/page.tsx
import { getDocuments } from '@/lib/api';

export default async function DocumentsPage() {
  const documents = await getDocuments();

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Documents</h1>
      {documents.map((doc) => (
        <DocumentCard key={doc.id} document={doc} />
      ))}
    </div>
  );
}
```

### Client Component (only when needed)

```typescript
'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';

export function UploadButton() {
  const [isUploading, setIsUploading] = useState(false);
  const { toast } = useToast();

  const handleUpload = async (file: File) => {
    setIsUploading(true);
    try {
      const res = await fetch('/api/documents', {
        method: 'POST',
        body: createFormData(file),
      });
      if (!res.ok) throw new Error('Upload failed');
      toast({ title: 'Document uploaded successfully' });
    } catch {
      toast({ title: 'Upload failed', variant: 'destructive' });
    } finally {
      setIsUploading(false);
    }
  };

  return <Button disabled={isUploading} onClick={() => /* trigger file input */}>Upload</Button>;
}
```

### API Client

```typescript
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;

export async function apiClient<T>(
  endpoint: string,
  options: { method?: string; body?: unknown; headers?: Record<string, string> } = {},
): Promise<{ data?: T; error?: string }> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: options.method || 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  const data = await response.json();
  return response.ok ? { data } : { error: data.detail || data.message };
}
```

---

## Common Pitfalls

### 1. Missing tenant_id in MongoDB Queries

```python
# WRONG — Leaks data across tenants
results = await db.chunks.find({"document_id": doc_id}).to_list(100)

# CORRECT — Always filter by tenant
results = await db.chunks.find({"document_id": doc_id, "tenant_id": tenant_id}).to_list(100)
```

### 2. Embedding Format

```python
# WRONG — JSON string
await db.chunks.insert_one({"embedding": json.dumps(embedding)})

# CORRECT — Native Python list
await db.chunks.insert_one({"embedding": embedding})  # list[float]
```

### 3. Missing Await on Async Operations

```python
# WRONG — Returns coroutine, not result
result = db.documents.find_one({"_id": doc_id})

# CORRECT
result = await db.documents.find_one({"_id": doc_id})
```

### 4. Using Sync MongoDB Driver

```python
# WRONG — Blocks the event loop
from pymongo import MongoClient

# CORRECT — Use motor for async
from motor.motor_asyncio import AsyncIOMotorClient
```
