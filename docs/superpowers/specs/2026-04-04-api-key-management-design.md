# API Key Generation, Validation, and Management

**Issue:** #8
**Date:** 2026-04-04
**Phase:** 3 (Multi-Tenancy & Auth)
**Priority:** Critical

## Overview

Build the API key system that authenticates requests from the embeddable widget and programmatic API access. API keys are scoped to a tenant and used instead of user sessions for external integrations.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Rate limiting | Deferred to #11 | YAGNI — #11 covers full metering & rate limiting |
| Key format | `mrag_` + 32 bytes base62 | Short, URL-safe, no special chars, matches issue spec |
| Auth header | `Authorization: Bearer mrag_...` | `mrag_` prefix is unambiguous discriminator vs JWT |
| Revocation | Soft delete (`is_revoked = True`) | Audit trail, prevents re-use, model already has field |
| `last_used_at` updates | Every request | MVP scale, fire-and-forget write, optimize later if needed |
| Frontend key management | Direct FastAPI calls | Consistent with existing auth pattern, no proxy needed |

## Key Generation & Storage

### Key Format

`mrag_` + 32 cryptographically random bytes, base62-encoded.

- Character set: `0-9a-zA-Z` (62 chars)
- Total length: ~48 chars (5-char prefix + ~43 encoded chars)
- Example: `mrag_7kB2xR9mQ4nLpW5vX8yZ1aB3cD6eF9gH0jK2mN4`

### Generation Flow

1. `secrets.token_bytes(32)` — 256 bits of entropy
2. Base62-encode the bytes
3. Prepend `mrag_` prefix
4. SHA-256 hash the full key string → `key_hash`
5. Extract first 8 chars after prefix → `key_prefix` (for UI identification)
6. Store `{ key_hash, key_prefix, name, permissions, tenant_id, is_revoked: false, created_at }` in `api_keys` collection
7. Return raw key **once** in the response — never stored or retrievable again

### Storage

Uses existing `ApiKeyModel` in `src/models/user.py`:

```python
class ApiKeyModel(BaseModel):
    tenant_id: str
    key_hash: str          # SHA256 hash of the API key
    key_prefix: str        # First 8 chars of key for identification
    name: str              # Human-readable key name
    permissions: list[str] # Default: ["chat", "search"]
    is_revoked: bool       # Soft delete flag
    last_used_at: Optional[datetime]
    created_at: datetime
```

### Index

Unique index on `api_keys.key_hash` for O(1) validation lookups. Must be created manually in Atlas UI.

## API Key Validation (Middleware)

### Updated `get_tenant_id()` in `src/core/tenant.py`

Current behavior (JWT-only) is extended with API key fallback:

1. Extract `Authorization: Bearer <token>` header
2. If token starts with `mrag_` → **API key path**
3. Otherwise → **JWT path** (existing logic, unchanged)

### API Key Path

1. SHA-256 hash the raw key
2. Look up `key_hash` in `api_keys` collection
3. If not found → 401 "Invalid API key"
4. If `is_revoked == True` → 401 "API key has been revoked"
5. Extract `tenant_id` from the document
6. Fire-and-forget `update_one` to set `last_used_at = utcnow()`
7. Return `tenant_id`

### Dependency Change

`get_tenant_id()` gains `deps: AgentDependencies = Depends(get_deps)` parameter. The DB lookup only happens on the API key path, so JWT-only requests stay fast (no DB call).

### Error Responses

| Condition | Status | Detail |
|-----------|--------|--------|
| Missing header | 401 | "Authorization header with Bearer token is required" |
| Invalid JWT | 401 | "Invalid or expired token" |
| Unknown API key | 401 | "Invalid API key" |
| Revoked API key | 401 | "API key has been revoked" |

## CRUD Endpoints

### Router

New file: `src/routers/keys.py` — prefix `/api/v1/keys`, tag `api-keys`.

All endpoints require **JWT auth** (dashboard users managing their keys via NextAuth sessions).

### POST /api/v1/keys

Create a new API key.

- **Request:** `{ name: str (2-100 chars), permissions: list[str] = ["chat", "search"] }`
- **Response (201):** `{ raw_key: "mrag_...", key_prefix: "7kB2xR9m", name, permissions, created_at }`
- The `raw_key` is shown once — frontend must warn user to copy it

### GET /api/v1/keys

List all keys for the authenticated tenant.

- **Response (200):** `{ keys: [{ id, key_prefix, name, permissions, is_revoked, last_used_at, created_at }] }`
- Includes revoked keys (frontend can show them greyed out)
- Sorted by `created_at` descending
- Never includes `key_hash` in response

### DELETE /api/v1/keys/{key_id}

Revoke a key (soft delete).

- `key_id` is the MongoDB `_id` (ObjectId as string)
- Sets `is_revoked = True` — does NOT delete the document
- Verifies the key belongs to the caller's `tenant_id` (tenant isolation)
- **Response (200):** `{ message: "API key revoked" }`
- **404** if key not found or wrong tenant

## APIKeyService

New file: `src/services/api_key.py` — follows the `AuthService` pattern.

```python
class APIKeyService:
    def __init__(self, api_keys_collection: AsyncCollection):
        self._api_keys = api_keys_collection
```

### Methods

| Method | Signature | Returns |
|--------|-----------|---------|
| `create_key` | `(tenant_id, name, permissions) -> dict` | `{ raw_key, key_prefix, name, permissions, created_at }` |
| `validate_key` | `(raw_key) -> dict \| None` | `{ tenant_id, permissions, key_id }` or `None` |
| `update_last_used` | `(key_hash) -> None` | Fire-and-forget timestamp update |
| `list_keys` | `(tenant_id) -> list[dict]` | All keys for tenant (excludes `key_hash`) |
| `revoke_key` | `(key_id, tenant_id) -> bool` | `True` if revoked, `False` if not found |

### Private Helper

`_generate_key() -> tuple[str, str, str]` — returns `(raw_key, key_hash, key_prefix)`.

Uses `secrets.token_bytes(32)` + base62 charset `0-9a-zA-Z`.

### Router Injection

```python
def _get_api_key_service(deps = Depends(get_deps)) -> APIKeyService:
    return APIKeyService(api_keys_collection=deps.api_keys_collection)
```

## Request/Response Models

Added to `src/models/api.py`:

| Model | Fields |
|-------|--------|
| `CreateKeyRequest` | `name: str (2-100), permissions: list[str] = ["chat", "search"]` |
| `CreateKeyResponse` | `raw_key, key_prefix, name, permissions, created_at` |
| `KeyResponse` | `id, key_prefix, name, permissions, is_revoked, last_used_at, created_at` |
| `KeyListResponse` | `keys: list[KeyResponse]` |

## File Changes

### New Files (4)

| File | Purpose |
|------|---------|
| `src/services/api_key.py` | APIKeyService class |
| `src/routers/keys.py` | CRUD endpoints for key management |
| `tests/test_api_key_service.py` | Service unit tests |
| `tests/test_api_key_router.py` | Router unit tests |

### Modified Files (3)

| File | Change |
|------|--------|
| `src/core/tenant.py` | Add `mrag_` prefix detection, API key validation path, `deps` parameter |
| `src/models/api.py` | Add `CreateKeyRequest`, `CreateKeyResponse`, `KeyResponse`, `KeyListResponse` |
| `src/main.py` | Register `keys.router` |

### Updated Test Files (1)

| File | Change |
|------|--------|
| `tests/test_tenant.py` | Add API key auth tests alongside existing JWT tests |

### Unchanged (Already in Place)

- `src/models/user.py` — `ApiKeyModel` already defined
- `src/core/dependencies.py` — `api_keys_collection` accessor exists
- `src/core/settings.py` — `mongodb_collection_api_keys` configured

## Test Plan

### `tests/test_api_key_service.py` (Unit)

- Create key → returns raw key with `mrag_` prefix, stores hash
- Create key → hash is SHA-256 of raw key (verify round-trip)
- Validate key → valid key returns tenant_id + permissions
- Validate key → unknown key returns None
- Validate key → revoked key returns None
- List keys → returns only keys for given tenant_id
- List keys → never includes `key_hash` in response
- Revoke key → sets `is_revoked = True`
- Revoke key → wrong tenant returns False (isolation)

### `tests/test_api_key_router.py` (Unit)

- POST /keys → 201 with raw key
- POST /keys → 401 without auth
- GET /keys → returns list for tenant
- GET /keys → empty list for new tenant
- DELETE /keys/{id} → 200 revokes key
- DELETE /keys/{id} → 404 for wrong tenant's key
- DELETE /keys/{id} → 404 for nonexistent key

### `tests/test_tenant.py` (Updated)

- API key in Bearer header → extracts tenant_id
- Revoked API key → 401
- Invalid `mrag_` key → 401
- JWT still works (regression)

## MongoDB Index

Unique index on `api_keys.key_hash` — must be created manually in Atlas UI or Atlas CLI. Cannot be created programmatically.
