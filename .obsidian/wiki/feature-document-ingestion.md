---
title: "Feature: Document Ingestion"
type: feature
tags: [feature, rag, ingestion, mongodb]
sources:
  - "apps/api/src/services/ingestion/"
  - "apps/api/src/services/blobstore/"
  - "apps/api/src/worker.py"
related:
  - "[[hybrid-rrf-search]]"
  - "[[feature-rag-agent]]"
  - "[[concept-ssrf-defense-url-ingestion]]"
  - "[[concept-celery-ingestion-worker]]"
  - "[[decision-blobstore-handoff]]"
created: 2026-04-29
updated: 2026-05-01
status: active
---

## Summary

The pipeline that turns customer-uploaded documents into searchable chunks. Docling parses many formats into markdown, the HybridChunker splits on semantic boundaries, embeddings are generated in batches via OpenAI, and both raw documents and chunks land in MongoDB scoped by `tenant_id`.

## GitHub Issues

| Issue | Title | Status |
|-------|-------|--------|
| — | (link issues here as they are created) | — |

## Key Decisions

- **Docling for parsing** — handles PDF, Word, PPT, Excel, HTML, audio uniformly into markdown
- **HybridChunker over fixed-size chunking** — preserves semantic boundaries and heading context, which improves retrieval relevance
- **OpenAI text-embedding-3-small (1536 dims)** — cost/quality tradeoff anchor; switching providers requires reindex
- **Native Python lists for embeddings** — never JSON strings (MongoDB's `$vectorSearch` requires native arrays)

## Implementation Notes

- Files:
  - `apps/api/src/services/ingestion/ingest.py` — orchestrator (Bug B fix shipped: failures raise instead of returning `[Error:…]` placeholder strings)
  - `apps/api/src/services/ingestion/chunker.py` — Docling HybridChunker wrapper
  - `apps/api/src/services/ingestion/embedder.py` — batch embedding generation
  - `apps/api/src/services/blobstore/` — `BlobStore` Protocol + `FilesystemBlobStore` + `SupabaseBlobStore` + factory + URI helpers; carries the upload from API → Celery worker via `blob_uri` (see `[[decision-blobstore-handoff]]`)
  - `apps/api/src/worker.py` — Celery tasks `ingest_document` and `ingest_url`; both receive `blob_uri:` (never `temp_path:`), assert tenant ownership, stream-download into local tmpfile, delete blob on success/terminal failure
- Storage:
  - `documents` — one row per uploaded file (title, source, content_hash for dedupe, metadata)
  - `chunks` — one row per chunk (`embedding[1536]`, `chunk_index`, `token_count`, references parent `document_id`)
- Indexes (must exist before queries work):
  - `vector_index` on `chunks.embedding` (Atlas UI; numDimensions: 1536, cosine)
  - Atlas Search text index on `chunks.content`
  - Compound `(tenant_id, document_id)` for tenant-scoped lookups
- Failure modes:
  - Docling can OOM on huge PDFs — chunk in streaming mode for files >50MB
  - OpenAI rate limits — batch size of 100 embeddings per request, exponential backoff
  - Vector indexes cannot be created programmatically — operator must create via Atlas UI/CLI

## Key Takeaways

- Embeddings are stored as Python lists (native MongoDB arrays), never JSON strings
- Re-ingesting the same document is idempotent via `content_hash`
- Vector index creation is a manual operator step — document this in deployment runbook

## See Also

- [[hybrid-rrf-search]] — consumes the chunks this pipeline produces
- [[feature-rag-agent]] — uses the search built on top of these embeddings
- [[concept-celery-ingestion-worker]] — the Celery tasks this pipeline runs inside
- [[decision-blobstore-handoff]] — how API and worker exchange the uploaded bytes
