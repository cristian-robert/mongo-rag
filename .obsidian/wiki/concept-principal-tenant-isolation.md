---
title: "Principal-based tenant isolation"
type: concept
tags: [concept, security, multi-tenancy, auth, principal]
sources:
  - "apps/api/src/core/principal.py"
  - "apps/api/src/core/authz.py"
  - "apps/api/src/core/middleware.py"
  - "apps/api/tests/test_tenant_filter_audit.py"
  - "PR #69 (centralize tenant_id via Principal + reject client tenant_id)"
related:
  - "[[multi-tenancy-tenant-isolation]]"
  - "[[decision-postgres-mongo-storage-split]]"
  - "[[decision-supabase-auth-over-nextauth]]"
  - "[[feature-api-key-management]]"
created: 2026-04-30
updated: 2026-04-30
status: compiled
---

## Overview

`Principal` is the immutable view of "who is making this request" derived from a verified JWT or API key. Every tenant-scoped database call MUST source `tenant_id` from a `Principal` — never from path/query/body input. Two layers enforce this: the `tenant_filter` / `tenant_doc` helpers at write time, and the `RejectClientTenantIdMiddleware` + AST audit test at the perimeter.

## Content

### Two Principal classes (intentional, but note the duplication)

There are TWO `Principal` dataclasses in the codebase — both frozen. Be aware which one you're importing:

1. **`src.core.principal.Principal`** (the one most code should use)
   - Frozen dataclass
   - Fields: `tenant_id: str`, `auth_method: str` (`"jwt"` or `"api_key"`), `user_id: Optional[str]`, `role: Optional[str]`, `permissions: tuple[str, ...]`, `api_key_id: Optional[str]`
   - Helpers: `require_jwt()` (raises 403 on API-key callers), `require_permission(p)` (raises 403 if API key lacks the permission tuple entry; JWT callers have implicit full access pending RBAC work)

2. **`src.core.authz.Principal`** (dashboard-only legacy)
   - Frozen dataclass with only `user_id`, `tenant_id`, `role`
   - Used by team and billing endpoints together with `require_role(UserRole.ADMIN)`-style decorators
   - Does NOT support API keys

`apps/api/src/routers/auth.py` imports BOTH. New endpoints should prefer `core.principal.Principal`; the dashboard-only one is kept for legacy compatibility.

### `tenant_filter` / `tenant_doc` (the write-time chokepoint)

```python
def tenant_filter(principal: Principal, **extra) -> dict[str, Any]:
    if not principal.tenant_id:
        raise HTTPException(401, ...)
    # extra["tenant_id"], if present and different, is OVERRIDDEN with a warning log
    return {**extra, "tenant_id": principal.tenant_id}

def tenant_doc(principal: Principal, **fields) -> dict[str, Any]:
    if not principal.tenant_id:
        raise HTTPException(401, ...)
    return {**fields, "tenant_id": principal.tenant_id}
```

Behavior worth knowing: if a caller passes `extra["tenant_id"]` that conflicts with `principal.tenant_id`, the helper **logs a warning and overrides** with the principal's value (rather than raising). This is a defense-in-depth choice — fail safe even when business code is wrong.

### `RejectClientTenantIdMiddleware` (the perimeter chokepoint)

`apps/api/src/core/middleware.py:124-223`. Refuses any request that even attempts to send `tenant_id`:

- **Path:** literal `/tenant_id/` segment anywhere → 400
- **Query:** `tenant_id` key in query params → 400
- **JSON body** (POST/PUT/PATCH only, `application/json`, NOT in `_TENANT_INPUT_BODY_EXEMPT_PREFIXES` like multipart upload routes):
  - Caps body scan at **1 MiB** (declared via Content-Length; larger bodies pass through untouched)
  - Recursive depth-bounded search (max depth **5**) for `tenant_id` key anywhere in the object graph
  - JSON parse failures are treated as "not present"
  - Re-attaches the consumed body so downstream handlers see it

Returns 400 with detail `"tenant_id is derived from auth — do not supply it"`.

### Audit test (`tests/test_tenant_filter_audit.py`)

Two tests run on every CI build:

1. **AST scan of every Mongo call site** in `apps/api/src/`. Calls to `find / find_one / find_one_and_* / update_* / delete_* / insert_* / aggregate / count_documents / replace_one / bulk_write` must:
   - Mention `tenant_id` in args / dict keys / kwargs / attributes, OR
   - Be inside a function whose body mentions `tenant_id`, OR
   - Use `tenant_filter(...)` / `tenant_doc(...)`, OR
   - Be on the documented allow-list (~17 entries — API-key lookup by hash, email/user lookup for login, public bot widget reads, migration bookkeeping, invite/WS-ticket claim by hash, signup atomicity)

2. **Router scan**: any router function with a `tenant_id` argument that lacks `Depends(...)` (or `Annotated[..., Depends(...)]`) fails the build.

### Auth methods that produce a Principal

- **JWT** (Supabase RS256/ES256/etc. via JWKS, OR legacy NextAuth HS256) — see `[[decision-supabase-auth-over-nextauth]]`
- **API key** (`mrag_*` prefix → bcrypt-hashed lookup in Postgres `api_keys`) — see `[[feature-api-key-management]]`

## Key Takeaways

- Two Principal classes exist; prefer `core.principal.Principal` for new code.
- `tenant_filter` overrides (with warning log) rather than rejecting a conflicting `tenant_id` — defense-in-depth.
- The middleware scans JSON bodies recursively to depth 5, with a 1 MiB cap.
- The audit test enforces the rule at the AST level on every Mongo call site; the allow-list has ~17 documented entries.
- The same Principal abstraction covers JWT and API-key auth methods, so business code never branches on `auth_method`.

## See Also

- [[multi-tenancy-tenant-isolation]] — broader tenant-isolation context
- [[decision-supabase-auth-over-nextauth]] — JWT side of the Principal (dual Supabase + NextAuth path)
- [[feature-api-key-management]] — API-key side of the Principal (bcrypt, Postgres-default)
- [[decision-postgres-mongo-storage-split]] — what stores the chokepoint protects
