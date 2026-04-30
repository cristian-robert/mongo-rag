---
title: "Feature: API Key Management"
type: feature
tags: [feature, auth, security, mongodb]
sources:
  - "git log: fc39d92 fix(api): restrict key management endpoints to JWT-only auth"
  - "git log: e439ab8 Enforce tenant isolation across all API endpoints (#39)"
related:
  - "[[multi-tenancy-tenant-isolation]]"
  - "[[concept-principal-tenant-isolation]]"
  - "[[decision-supabase-auth-over-nextauth]]"
  - "[[decision-postgres-mongo-storage-split]]"
created: 2026-04-29
updated: 2026-04-30
status: active
---

## Summary

Customers create and revoke API keys for the embeddable widget and programmatic access. Keys carry the `mrag_` prefix, are SHA-256 hashed at rest, and the management endpoints are intentionally JWT-only — you cannot rotate a key using the key itself.

## GitHub Issues

| Issue | Title | Status |
|-------|-------|--------|
| #38 | feature/api-key-management (PR) | merged |
| #39 | Enforce tenant isolation across all API endpoints | merged |

## Key Decisions

- **Prefix-display, hash-storage** — the `mrag_xxxx...` prefix is shown in the dashboard for identification; only the SHA-256 hash is in MongoDB. The full key value is shown to the user once at creation and never recoverable.
- **JWT-only on `/api/v1/keys/*` endpoints** — fix fc39d92 closed a privilege-escalation gap where an API key could rotate itself or other keys
- **Tenant isolation enforced on all endpoints** — fix e439ab8 audited every route to ensure `tenant_id` is derived from auth, never from request body

## Implementation Notes

- Storage: `api_keys` collection — `{ key_hash, prefix, name, tenant_id, created_at, last_used_at, revoked_at? }`
- Unique index on `key_hash`
- Auth flow:
  - Dashboard mutations (create/list/revoke) → JWT cookie auth → derives `tenant_id` from claims
  - Widget / programmatic reads → API key in `X-API-Key` header → SHA-256 hash → `api_keys.find_one({"key_hash": h})` → derives `tenant_id`
- The two auth paths share a `get_current_tenant` resolver but never overlap — `/keys/*` endpoints reject API-key auth

## Key Takeaways

- The full API key value is a one-time secret — show in toast/modal at creation, never store, never show again
- Always pass `tenant_id` from the auth resolver into the query, never from request body
- API keys cannot manage other API keys — that's the JWT-only invariant from fc39d92

## See Also

- [[multi-tenancy-tenant-isolation]] — the broader pattern this feature depends on
