---
title: "Multi-Tenancy: Tenant Isolation"
type: concept
tags: [multi-tenancy, security, mongodb]
sources:
  - "CLAUDE.md core principle #4"
  - "apps/api/src/dependencies.py"
related:
  - "[[feature-api-key-management]]"
  - "[[hybrid-rrf-search]]"
created: 2026-04-29
updated: 2026-04-29
status: active
---

## Summary

MongoRAG runs all customers on a shared MongoDB cluster. Tenant isolation is enforced at the **query layer**, not by separate databases. Every document in tenant-scoped collections carries a `tenant_id` field, and every read or write must filter on it. This is the most critical security boundary in the system.

## Content

### Tenant-scoped collections

`documents`, `chunks`, `conversations`, `api_keys`, `users`, `subscriptions` — all carry `tenant_id`. Only `tenants` (the registry) does not.

### Where tenant_id comes from

- **Dashboard requests:** authenticated session → `tenant_id` in JWT claims
- **Widget / programmatic requests:** API key → look up `api_keys` collection by `key_hash` → read `tenant_id` from the matching row

Never trust a tenant_id sent from the client body or query string. The FastAPI dependency `get_current_tenant` is the single trusted source.

### The rule

Every MongoDB query that touches a tenant-scoped collection must include `tenant_id` in the filter — even reads that look "internal," even aggregation pipelines, even the `$vectorSearch` filter (push it in, never post-filter).

### Common bug

```python
# WRONG — leaks across tenants when document_id collides
results = await db.chunks.find({"document_id": doc_id}).to_list(100)

# CORRECT
results = await db.chunks.find({"document_id": doc_id, "tenant_id": tenant_id}).to_list(100)
```

### Atlas Search and Vector Search

For `$search` and `$vectorSearch` you cannot filter after the fact — you must push the tenant filter into the operator's `filter` clause so the search engine restricts the candidate set before ranking.

## Key Takeaways

- Tenant ID is derived from auth, never from request body
- Every tenant-scoped collection write and read includes `tenant_id`
- Push tenant filters into `$vectorSearch.filter`, not into a post-`$match` stage

## See Also

- [[feature-api-key-management]] — derives tenant_id from API keys
- [[hybrid-rrf-search]] — pushes tenant_id into both search operators
