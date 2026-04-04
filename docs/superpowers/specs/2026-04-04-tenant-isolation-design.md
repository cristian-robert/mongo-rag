# Tenant Isolation Hardening — Design Spec

**Issue:** #9 — Enforce tenant isolation across all API endpoints
**Date:** 2026-04-04
**Approach:** Surgical fixes + Tenant Guard Middleware (Approach B)

## Context

The MongoRAG API already has good tenant isolation in most areas — chat, ingest, keys, and all search endpoints properly filter by `tenant_id` via dependency injection. However, an audit revealed 4 critical gaps and several medium-priority improvements needed.

### Current State

**Already isolated:**
- POST `/api/v1/chat` — `get_tenant_id()` dependency, passed to search/conversation services
- POST `/api/v1/documents/ingest` — `get_tenant_id()` dependency, all queries filtered
- GET `/api/v1/documents/{id}/status` — `get_tenant_id()` dependency
- POST/GET/DELETE `/api/v1/keys` — `get_tenant_id_from_jwt()` dependency (JWT-only)
- Semantic search — `$vectorSearch` filter includes `tenant_id`
- Text search — `$search` compound filter includes `tenant_id`
- Hybrid search — delegates to semantic + text, both filtered

**Gaps identified:**
1. WebSocket `/chat/ws` — accepts `tenant_id` as query param with zero auth
2. Login — queries users by email only, no tenant disambiguation
3. Forgot/reset password — email-only lookup, tokens not tenant-scoped
4. No safety net for future endpoints that forget tenant context

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Email uniqueness | Global (one account per email) | Simplifies auth, natural for SaaS where signup creates one tenant per user |
| WebSocket auth | JWT/API key in query param | Standard pattern — browsers can't send headers on WebSocket upgrade |
| Tenant enforcement | Explicit DI + guard middleware | Keep working explicit pattern, add safety net for future endpoints |
| DB operations wrapper | Not needed | Codebase is small, explicit passing is clearer than magic abstraction |

---

## Section 1: Global Email Uniqueness

### Problem
Login queries `users` collection by email only (`find_one({"email": email})`). If the same email exists in two tenants, MongoDB returns whichever it finds first — potential cross-tenant auth bypass.

### Solution
- Add a **unique index** on `users.email` at the database level
- **Signup:** Catch `DuplicateKeyError` → return clear "email already registered" error (HTTP 409)
- **Login:** `find_one({"email": email})` becomes safe — only one user per email exists, and the `tenant_id` on that document is authoritative
- **Forgot/reset password:** Same — email lookup returns the correct (only) user

### Files Modified
- `src/core/database.py` — add unique index creation on startup
- `src/services/auth.py` — handle `DuplicateKeyError` in signup

---

## Section 2: WebSocket Authentication

### Problem
`/chat/ws` accepts `tenant_id` as a raw query parameter. Anyone can connect and impersonate any tenant — complete isolation bypass.

### Solution
- Client connects with `ws://host/api/v1/chat/ws?token=<jwt_or_api_key>`
- On connection, before `websocket.accept()`:
  1. Extract `token` from query params
  2. If token starts with `mrag_` → resolve via `_resolve_api_key()`
  3. Otherwise → validate JWT via `_resolve_jwt()`
  4. Extract `tenant_id` from result
  5. If invalid/missing → `websocket.close(code=4001, reason="...")`
- Remove the `tenant_id` query parameter entirely

### Breaking Change
Frontend/widget clients must send JWT or API key instead of raw `tenant_id`. This is necessary — the current behavior is a vulnerability.

### Files Modified
- `src/routers/chat.py` — rewrite WebSocket handler auth logic
- `src/core/tenant.py` — extract auth resolution functions for reuse (may already be importable)

---

## Section 3: Password Reset Tenant Scoping

### Problem
`PasswordResetTokenModel` has no `tenant_id` field. Even with global email uniqueness making the email lookup safe, tokens should be scoped to tenants for defense in depth.

### Solution
- Add `tenant_id: str` field to `PasswordResetTokenModel`
- **Forgot password flow:** After finding user by email, store `tenant_id` from user doc into the reset token document
- **Reset password flow:** When validating token, verify `tenant_id` matches the user being updated
- Add index on `reset_tokens.token_hash` for lookup performance

### Files Modified
- `src/models/user.py` — add `tenant_id` to `PasswordResetTokenModel`
- `src/services/auth.py` — include `tenant_id` when creating/validating reset tokens

---

## Section 4: Tenant Guard Middleware

### Purpose
Safety net that catches future endpoints missing tenant context. Not primary enforcement — that remains the explicit `get_tenant_id()` dependency.

### How It Works
1. `get_tenant_id()` and `get_tenant_id_from_jwt()` accept `Request` parameter and set `request.state.tenant_id` after successful auth
2. `TenantGuardMiddleware` runs on every response:
   - Checks if route is under `/api/v1/` and NOT in exempt list
   - Verifies `request.state.tenant_id` was set
   - **Dev mode** (`DEBUG=true`): raises error
   - **Prod mode**: logs warning with route path — never blocks user requests

### Exempt Routes
- `/api/v1/auth/*` — pre-authentication endpoints
- `/health` — public health check

### Files Modified
- `src/core/tenant.py` — modify auth dependencies to set `request.state.tenant_id`
- `src/core/middleware.py` — new file, `TenantGuardMiddleware` class (~30 lines)
- `src/main.py` — register middleware

---

## Section 5: Negative Tests

### Purpose
Verify that Tenant A cannot access Tenant B's data. The most important deliverable for this issue.

### Test File
`tests/test_tenant_isolation.py`

### Fixtures
- Create Tenant A with user, documents, chunks, conversation, API key
- Create Tenant B with user, documents, chunks, conversation, API key
- Generate JWT tokens for both tenants

### Test Cases

| # | Test | Verifies |
|---|------|----------|
| 1 | Chat with Tenant A's token returns only Tenant A's search results | Chat isolation |
| 2 | Document status with Tenant A's token returns 404 for Tenant B's document | Document isolation |
| 3 | List keys with Tenant A's JWT shows only Tenant A's keys | API key isolation |
| 4 | Revoke key with Tenant A's JWT fails for Tenant B's key ID | API key cross-tenant |
| 5 | WebSocket with Tenant A's token only searches Tenant A's chunks | WebSocket isolation |
| 6 | Semantic search returns only authenticated tenant's chunks | Search isolation |
| 7 | Text search returns only authenticated tenant's chunks | Search isolation |
| 8 | Hybrid search returns only authenticated tenant's chunks | Search isolation |
| 9 | Signup with existing email returns 409 | Email uniqueness |
| 10 | Reset token contains `tenant_id` matching the user | Reset token scoping |
| 11 | Unprotected `/api/v1/` endpoint triggers tenant guard warning | Guard middleware |

### Approach
Integration tests using `httpx.AsyncClient` with FastAPI's `TestClient`. Test MongoDB database with isolated collections.

---

## Section 6: Database Indexes

### New Indexes

| Collection | Index | Type | Purpose |
|---|---|---|---|
| `users` | `{"email": 1}` | Unique | Global email uniqueness enforcement |
| `documents` | `{"tenant_id": 1, "created_at": -1}` | Compound | Tenant-scoped document listing |
| `chunks` | `{"tenant_id": 1, "document_id": 1}` | Compound | Tenant-scoped chunk lookups |
| `conversations` | `{"tenant_id": 1, "created_at": -1}` | Compound | Tenant-scoped conversation queries |
| `api_keys` | `{"tenant_id": 1}` | Regular | Tenant-scoped key listing |
| `reset_tokens` | `{"token_hash": 1}` | Regular | Token lookup performance |
| `reset_tokens` | `{"expires_at": 1}` | TTL (24h) | Auto-cleanup of expired tokens after 24 hours |

### Implementation
- Startup function in `src/core/database.py` using `create_index(background=True)`
- `create_index()` is idempotent — safe to run on every app startup
- Vector search and Atlas Search indexes remain managed via Atlas UI

### Files Modified
- `src/core/database.py` — add `ensure_indexes()` function, call from startup

---

## Files Changed Summary

| File | Change |
|------|--------|
| `src/core/database.py` | Add `ensure_indexes()` with all indexes, call on startup |
| `src/core/tenant.py` | Set `request.state.tenant_id` in auth dependencies |
| `src/core/middleware.py` | New — `TenantGuardMiddleware` |
| `src/main.py` | Register `TenantGuardMiddleware` |
| `src/models/user.py` | Add `tenant_id` to `PasswordResetTokenModel` |
| `src/services/auth.py` | Handle `DuplicateKeyError` in signup, scope reset tokens |
| `src/routers/chat.py` | Rewrite WebSocket auth (JWT/API key from query param) |
| `tests/test_tenant_isolation.py` | New — 11 negative isolation test cases |

## Out of Scope
- Repository pattern / `TenantScopedCollection` abstraction — not needed at current scale
- Row-level security at database level — MongoDB doesn't support this natively
- Per-tenant database separation — overkill for current architecture
