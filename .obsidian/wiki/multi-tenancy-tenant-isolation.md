---
title: "Multi-Tenancy: Tenant Isolation"
type: concept
tags: [multi-tenancy, security, mongodb]
sources:
  - "CLAUDE.md core principle #4"
  - "apps/api/src/core/principal.py"
  - "apps/api/src/core/middleware.py (RejectClientTenantIdMiddleware)"
  - "apps/api/tests/test_tenant_filter_audit.py"
related:
  - "[[feature-api-key-management]]"
  - "[[hybrid-rrf-search]]"
  - "[[concept-principal-tenant-isolation]]"
  - "[[decision-postgres-mongo-storage-split]]"
created: 2026-04-29
updated: 2026-04-30
status: active
---

## Summary

MongoRAG runs all customers on a shared MongoDB cluster. Tenant isolation is enforced at the **query layer**, not by separate databases. Every document in tenant-scoped collections carries a `tenant_id` field, and every read or write must filter on it. This is the most critical security boundary in the system.

## Content

### Tenant-scoped storage

After the foundation sprint, identity/billing moved to Postgres while RAG content stayed in Mongo (see [[decision-postgres-mongo-storage-split]]). Both stores carry `tenant_id` on every tenant-scoped row/document:

- **Mongo tenant-scoped:** `documents`, `chunks`, `conversations`, `bots`
- **Postgres tenant-scoped:** `users`, `team_members`, `api_keys`, `subscriptions` (and `stripe_events` is keyed by Stripe event id, not tenant)
- **Not tenant-scoped:** `tenants` itself (the registry)

### Where tenant_id comes from

- **Dashboard requests:** Supabase JWT → `tenant_id` in claims (see [[decision-supabase-auth-over-nextauth]])
- **Widget / programmatic requests:** API key → look up Postgres `api_keys` row by `key_hash` → read `tenant_id` from the matching row

Never trust a tenant_id sent from the client body or query string. The FastAPI dependencies `get_principal` and `get_tenant_id` in `apps/api/src/core/principal.py` and `apps/api/src/core/tenant.py` are the only trusted sources.

### Server-side chokepoints (post-#44)

1. **Principal dataclass** — frozen view of the authenticated caller (tenant_id, auth_method, user_id, role, permissions). Built only from a verified JWT or API-key lookup.
2. **tenant_filter(principal, ...)** and **tenant_doc(principal, ...)** helpers — every Mongo filter / insert that touches tenant data should be built through these so tenant_id cannot drift.
3. **RejectClientTenantIdMiddleware** — refuses any inbound request that places tenant_id in the query string, path, or JSON body. Returns HTTP 400 — fails closed instead of silently overriding.
4. **tests/test_tenant_filter_audit.py** — static AST audit that scans every .py file in apps/api/src/ for raw Mongo CRUD calls without tenant_id. Failures must be fixed or justified on the documented allowlist.

### The rule

Every MongoDB query that touches a tenant-scoped collection must include `tenant_id` in the filter — even reads that look "internal," even aggregation pipelines, even the `$vectorSearch` filter (push it in, never post-filter).

### Common bug

```python
# WRONG — leaks across tenants when document_id collides
results = await db.chunks.find({"document_id": doc_id}).to_list(100)

# CORRECT (helper enforces the principal's tenant_id)
filt = tenant_filter(principal, document_id=doc_id)
results = await db.chunks.find(filt).to_list(100)
```

### Atlas Search and Vector Search

For `$search` and `$vectorSearch` you cannot filter after the fact — you must push the tenant filter into the operator's `filter` clause so the search engine restricts the candidate set before ranking.

## Key Takeaways

- Tenant ID is derived from auth, never from request body
- Every tenant-scoped collection write and read includes `tenant_id`
- Push tenant filters into `$vectorSearch.filter`, not into a post-`$match` stage
- Use `tenant_filter(principal, ...)` / `tenant_doc(principal, ...)` for new query sites; the AST audit will block PRs that skip them
- `RejectClientTenantIdMiddleware` fails closed on any forged `tenant_id` in the request

## See Also

- [[concept-principal-tenant-isolation]] — the chokepoint dataclass + helpers this pattern relies on
- [[decision-postgres-mongo-storage-split]] — which store each tenant-scoped table lives in
- [[decision-supabase-auth-over-nextauth]] — JWT side of the Principal
- [[feature-api-key-management]] — derives tenant_id from API keys
- [[hybrid-rrf-search]] — pushes tenant_id into both search operators
