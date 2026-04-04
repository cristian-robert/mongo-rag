# API Key Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the API key system for authenticating widget and programmatic requests — key generation, SHA-256 storage, validation middleware, and CRUD endpoints.

**Architecture:** Single `APIKeyService` class handles all key operations. `get_tenant_id()` middleware detects `mrag_` prefix in Bearer token to route between JWT and API key auth. New `/api/v1/keys` router for CRUD. TDD throughout.

**Tech Stack:** FastAPI, MongoDB (async via pymongo), SHA-256 hashing, secrets module, base62 encoding, pytest with AsyncMock

**Spec:** `docs/superpowers/specs/2026-04-04-api-key-management-design.md`
**Issue:** #8

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `src/services/api_key.py` | Create | APIKeyService: generate, validate, list, revoke keys |
| `src/routers/keys.py` | Create | CRUD endpoints: POST/GET/DELETE /api/v1/keys |
| `src/models/api.py` | Modify | Add CreateKeyRequest, CreateKeyResponse, KeyResponse, KeyListResponse |
| `src/core/tenant.py` | Modify | Add `mrag_` prefix detection, API key validation path |
| `src/main.py` | Modify | Register keys router |
| `tests/test_api_key_service.py` | Create | Unit tests for APIKeyService |
| `tests/test_api_key_router.py` | Create | Unit tests for keys router |
| `tests/test_tenant.py` | Modify | Add API key auth tests |
| `tests/conftest.py` | Modify | Add `api_keys_collection` mock to `mock_deps` |

**Already in place (no changes needed):**
- `src/models/user.py` — `ApiKeyModel` defined
- `src/core/dependencies.py` — `api_keys_collection` property exists
- `src/core/settings.py` — `mongodb_collection_api_keys` configured

---

### Task 1: Request/Response Models

**Files:**
- Modify: `apps/api/src/models/api.py`

- [ ] **Step 1: Add API key request/response models to `src/models/api.py`**

Add the following after the `MessageResponse` class at the end of the file:

```python
# --- API Keys ---


class CreateKeyRequest(BaseModel):
    """Request body for creating an API key."""

    name: str = Field(..., min_length=2, max_length=100, description="Human-readable key name")
    permissions: list[str] = Field(
        default_factory=lambda: ["chat", "search"],
        description="Allowed operations",
    )


class CreateKeyResponse(BaseModel):
    """Response from key creation (raw key shown once)."""

    raw_key: str = Field(..., description="Full API key — shown only once")
    key_prefix: str = Field(..., description="First 8 chars for identification")
    name: str
    permissions: list[str]
    created_at: datetime


class KeyResponse(BaseModel):
    """A single API key's metadata (no raw key or hash)."""

    id: str = Field(..., description="Key document ID")
    key_prefix: str = Field(..., description="First 8 chars for identification")
    name: str
    permissions: list[str]
    is_revoked: bool
    last_used_at: Optional[datetime] = None
    created_at: datetime


class KeyListResponse(BaseModel):
    """List of API keys for a tenant."""

    keys: list[KeyResponse]
```

Also add `datetime` to the imports at the top of the file:

```python
from datetime import datetime
from typing import Literal, Optional
```

- [ ] **Step 2: Verify the models import cleanly**

Run: `cd apps/api && uv run python -c "from src.models.api import CreateKeyRequest, CreateKeyResponse, KeyResponse, KeyListResponse; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```
git add apps/api/src/models/api.py
git commit -m "feat(api): add API key request/response models"
```

---

### Task 2: APIKeyService — Key Generation

**Files:**
- Create: `apps/api/src/services/api_key.py`
- Create: `apps/api/tests/test_api_key_service.py`

- [ ] **Step 1: Write failing tests for key generation**

Create `apps/api/tests/test_api_key_service.py`:

```python
"""Tests for API key service."""

import hashlib
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_api_keys_collection():
    """Create mock api_keys collection."""
    collection = MagicMock()
    collection.insert_one = AsyncMock()
    collection.find_one = AsyncMock(return_value=None)
    collection.update_one = AsyncMock()
    return collection


@pytest.mark.unit
async def test_create_key_returns_raw_key_with_prefix(mock_api_keys_collection):
    """create_key returns a raw key starting with 'mrag_'."""
    from src.services.api_key import APIKeyService

    service = APIKeyService(api_keys_collection=mock_api_keys_collection)
    result = await service.create_key(
        tenant_id="tenant-abc", name="Test Key", permissions=["chat", "search"]
    )

    assert result["raw_key"].startswith("mrag_")
    assert len(result["raw_key"]) > 20
    assert result["name"] == "Test Key"
    assert result["permissions"] == ["chat", "search"]
    assert result["key_prefix"] == result["raw_key"][5:13]  # First 8 chars after 'mrag_'
    assert result["created_at"] is not None


@pytest.mark.unit
async def test_create_key_stores_sha256_hash(mock_api_keys_collection):
    """create_key stores SHA-256 hash of the raw key, not the key itself."""
    from src.services.api_key import APIKeyService

    service = APIKeyService(api_keys_collection=mock_api_keys_collection)
    result = await service.create_key(
        tenant_id="tenant-abc", name="Test Key", permissions=["chat"]
    )

    # Verify insert_one was called
    mock_api_keys_collection.insert_one.assert_called_once()
    stored_doc = mock_api_keys_collection.insert_one.call_args[0][0]

    # Verify hash matches
    expected_hash = hashlib.sha256(result["raw_key"].encode()).hexdigest()
    assert stored_doc["key_hash"] == expected_hash

    # Verify raw key is NOT stored
    assert "raw_key" not in stored_doc
    assert stored_doc["tenant_id"] == "tenant-abc"
    assert stored_doc["is_revoked"] is False


@pytest.mark.unit
async def test_create_key_generates_unique_keys(mock_api_keys_collection):
    """Each call to create_key generates a different raw key."""
    from src.services.api_key import APIKeyService

    service = APIKeyService(api_keys_collection=mock_api_keys_collection)
    result1 = await service.create_key(
        tenant_id="tenant-abc", name="Key 1", permissions=["chat"]
    )
    result2 = await service.create_key(
        tenant_id="tenant-abc", name="Key 2", permissions=["chat"]
    )

    assert result1["raw_key"] != result2["raw_key"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && uv run pytest tests/test_api_key_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.services.api_key'`

- [ ] **Step 3: Implement APIKeyService with key generation**

Create `apps/api/src/services/api_key.py`:

```python
"""API key service: generation, validation, listing, revocation."""

import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from pymongo.asynchronous.collection import AsyncCollection

logger = logging.getLogger(__name__)

# Base62 alphabet: 0-9, A-Z, a-z
_BASE62_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def _base62_encode(data: bytes) -> str:
    """Encode bytes to base62 string."""
    num = int.from_bytes(data, byteorder="big")
    if num == 0:
        return _BASE62_ALPHABET[0]
    chars = []
    while num > 0:
        num, remainder = divmod(num, 62)
        chars.append(_BASE62_ALPHABET[remainder])
    return "".join(reversed(chars))


def _generate_key() -> tuple[str, str, str]:
    """Generate a new API key.

    Returns:
        Tuple of (raw_key, key_hash, key_prefix).
    """
    raw_bytes = secrets.token_bytes(32)
    encoded = _base62_encode(raw_bytes)
    raw_key = f"mrag_{encoded}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = encoded[:8]
    return raw_key, key_hash, key_prefix


class APIKeyService:
    """Handles API key generation, validation, listing, and revocation."""

    def __init__(self, api_keys_collection: AsyncCollection) -> None:
        self._api_keys = api_keys_collection

    async def create_key(
        self, tenant_id: str, name: str, permissions: list[str]
    ) -> dict[str, Any]:
        """Generate a new API key and store its hash.

        Args:
            tenant_id: Tenant this key belongs to.
            name: Human-readable key name.
            permissions: Allowed operations.

        Returns:
            Dict with raw_key (shown once), key_prefix, name, permissions, created_at.
        """
        raw_key, key_hash, key_prefix = _generate_key()
        now = datetime.now(timezone.utc)

        doc = {
            "tenant_id": tenant_id,
            "key_hash": key_hash,
            "key_prefix": key_prefix,
            "name": name,
            "permissions": permissions,
            "is_revoked": False,
            "last_used_at": None,
            "created_at": now,
        }
        await self._api_keys.insert_one(doc)

        logger.info(
            "api_key_created",
            extra={"tenant_id": tenant_id, "key_prefix": key_prefix, "name": name},
        )

        return {
            "raw_key": raw_key,
            "key_prefix": key_prefix,
            "name": name,
            "permissions": permissions,
            "created_at": now,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/api && uv run pytest tests/test_api_key_service.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```
git add apps/api/src/services/api_key.py apps/api/tests/test_api_key_service.py
git commit -m "feat(api): add APIKeyService with key generation and tests"
```

---

### Task 3: APIKeyService — Key Validation

**Files:**
- Modify: `apps/api/tests/test_api_key_service.py`
- Modify: `apps/api/src/services/api_key.py`

- [ ] **Step 1: Write failing tests for key validation**

Append to `apps/api/tests/test_api_key_service.py`:

```python
@pytest.mark.unit
async def test_validate_key_returns_tenant_data(mock_api_keys_collection):
    """validate_key returns tenant_id and permissions for a valid key."""
    from src.services.api_key import APIKeyService

    raw_key = "mrag_testkey12345678901234567890123456"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    mock_api_keys_collection.find_one.return_value = {
        "_id": ObjectId(),
        "tenant_id": "tenant-abc",
        "key_hash": key_hash,
        "permissions": ["chat", "search"],
        "is_revoked": False,
    }

    service = APIKeyService(api_keys_collection=mock_api_keys_collection)
    result = await service.validate_key(raw_key)

    assert result is not None
    assert result["tenant_id"] == "tenant-abc"
    assert result["permissions"] == ["chat", "search"]
    assert "key_id" in result

    # Verify lookup used the hash
    mock_api_keys_collection.find_one.assert_called_once_with({"key_hash": key_hash})


@pytest.mark.unit
async def test_validate_key_unknown_returns_none(mock_api_keys_collection):
    """validate_key returns None for an unknown key."""
    from src.services.api_key import APIKeyService

    mock_api_keys_collection.find_one.return_value = None

    service = APIKeyService(api_keys_collection=mock_api_keys_collection)
    result = await service.validate_key("mrag_nonexistentkey1234567890123456")

    assert result is None


@pytest.mark.unit
async def test_validate_key_revoked_returns_none(mock_api_keys_collection):
    """validate_key returns None for a revoked key."""
    from src.services.api_key import APIKeyService

    raw_key = "mrag_revokedkey12345678901234567890123"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    mock_api_keys_collection.find_one.return_value = {
        "_id": ObjectId(),
        "tenant_id": "tenant-abc",
        "key_hash": key_hash,
        "permissions": ["chat"],
        "is_revoked": True,
    }

    service = APIKeyService(api_keys_collection=mock_api_keys_collection)
    result = await service.validate_key(raw_key)

    assert result is None
```

Add `from bson import ObjectId` to the imports at the top of the test file.

- [ ] **Step 2: Run tests to verify new tests fail**

Run: `cd apps/api && uv run pytest tests/test_api_key_service.py::test_validate_key_returns_tenant_data -v`
Expected: FAIL — `AttributeError: 'APIKeyService' object has no attribute 'validate_key'`

- [ ] **Step 3: Implement validate_key and update_last_used**

Add to `APIKeyService` class in `apps/api/src/services/api_key.py`:

```python
    async def validate_key(self, raw_key: str) -> Optional[dict[str, Any]]:
        """Validate an API key and return tenant data.

        Args:
            raw_key: The full API key string (e.g., mrag_...).

        Returns:
            Dict with tenant_id, permissions, key_id if valid; None otherwise.
        """
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        doc = await self._api_keys.find_one({"key_hash": key_hash})

        if not doc:
            return None

        if doc.get("is_revoked", False):
            return None

        return {
            "tenant_id": doc["tenant_id"],
            "permissions": doc["permissions"],
            "key_id": str(doc["_id"]),
        }

    async def update_last_used(self, key_hash: str) -> None:
        """Update the last_used_at timestamp for a key.

        Args:
            key_hash: SHA-256 hash of the API key.
        """
        await self._api_keys.update_one(
            {"key_hash": key_hash},
            {"$set": {"last_used_at": datetime.now(timezone.utc)}},
        )
```

- [ ] **Step 4: Run all service tests**

Run: `cd apps/api && uv run pytest tests/test_api_key_service.py -v`
Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```
git add apps/api/src/services/api_key.py apps/api/tests/test_api_key_service.py
git commit -m "feat(api): add API key validation and last_used tracking"
```

---

### Task 4: APIKeyService — List and Revoke

**Files:**
- Modify: `apps/api/tests/test_api_key_service.py`
- Modify: `apps/api/src/services/api_key.py`

- [ ] **Step 1: Write failing tests for list and revoke**

Append to `apps/api/tests/test_api_key_service.py`:

```python
@pytest.mark.unit
async def test_list_keys_returns_tenant_keys(mock_api_keys_collection):
    """list_keys returns keys for the given tenant only."""
    from src.services.api_key import APIKeyService

    key_id = ObjectId()
    mock_cursor = MagicMock()
    mock_cursor.sort = MagicMock(return_value=mock_cursor)
    mock_cursor.to_list = AsyncMock(
        return_value=[
            {
                "_id": key_id,
                "tenant_id": "tenant-abc",
                "key_prefix": "7kB2xR9m",
                "name": "Production",
                "permissions": ["chat", "search"],
                "is_revoked": False,
                "last_used_at": None,
                "created_at": datetime(2026, 4, 1, tzinfo=timezone.utc),
            }
        ]
    )
    mock_api_keys_collection.find = MagicMock(return_value=mock_cursor)

    service = APIKeyService(api_keys_collection=mock_api_keys_collection)
    result = await service.list_keys("tenant-abc")

    assert len(result) == 1
    assert result[0]["id"] == str(key_id)
    assert result[0]["key_prefix"] == "7kB2xR9m"
    assert result[0]["name"] == "Production"
    assert "key_hash" not in result[0]

    # Verify query filtered by tenant_id and projected out key_hash
    mock_api_keys_collection.find.assert_called_once()
    find_args = mock_api_keys_collection.find.call_args
    assert find_args[0][0] == {"tenant_id": "tenant-abc"}
    assert find_args[0][1]["key_hash"] == 0  # Projected out


@pytest.mark.unit
async def test_revoke_key_sets_is_revoked(mock_api_keys_collection):
    """revoke_key sets is_revoked=True for the correct key and tenant."""
    from src.services.api_key import APIKeyService

    key_id = ObjectId()
    mock_api_keys_collection.update_one.return_value = MagicMock(matched_count=1)

    service = APIKeyService(api_keys_collection=mock_api_keys_collection)
    result = await service.revoke_key(str(key_id), "tenant-abc")

    assert result is True

    mock_api_keys_collection.update_one.assert_called_once()
    call_args = mock_api_keys_collection.update_one.call_args
    assert call_args[0][0] == {"_id": key_id, "tenant_id": "tenant-abc"}
    assert call_args[0][1] == {"$set": {"is_revoked": True}}


@pytest.mark.unit
async def test_revoke_key_wrong_tenant_returns_false(mock_api_keys_collection):
    """revoke_key returns False when key doesn't belong to tenant."""
    from src.services.api_key import APIKeyService

    key_id = ObjectId()
    mock_api_keys_collection.update_one.return_value = MagicMock(matched_count=0)

    service = APIKeyService(api_keys_collection=mock_api_keys_collection)
    result = await service.revoke_key(str(key_id), "wrong-tenant")

    assert result is False
```

Add `from datetime import datetime, timezone` to the imports at the top of the test file.

- [ ] **Step 2: Run tests to verify new tests fail**

Run: `cd apps/api && uv run pytest tests/test_api_key_service.py::test_list_keys_returns_tenant_keys -v`
Expected: FAIL — `AttributeError: 'APIKeyService' object has no attribute 'list_keys'`

- [ ] **Step 3: Implement list_keys and revoke_key**

Add to `APIKeyService` class in `apps/api/src/services/api_key.py`:

```python
    async def list_keys(self, tenant_id: str) -> list[dict[str, Any]]:
        """List all API keys for a tenant.

        Args:
            tenant_id: Tenant to list keys for.

        Returns:
            List of key metadata dicts (excludes key_hash).
        """
        cursor = self._api_keys.find(
            {"tenant_id": tenant_id},
            {"key_hash": 0},  # Never return the hash
        ).sort("created_at", -1)

        keys = await cursor.to_list(length=100)

        return [
            {
                "id": str(doc["_id"]),
                "key_prefix": doc["key_prefix"],
                "name": doc["name"],
                "permissions": doc["permissions"],
                "is_revoked": doc["is_revoked"],
                "last_used_at": doc.get("last_used_at"),
                "created_at": doc["created_at"],
            }
            for doc in keys
        ]

    async def revoke_key(self, key_id: str, tenant_id: str) -> bool:
        """Revoke an API key (soft delete).

        Args:
            key_id: MongoDB _id of the key document.
            tenant_id: Tenant the key must belong to (isolation guard).

        Returns:
            True if key was revoked, False if not found or wrong tenant.
        """
        result = await self._api_keys.update_one(
            {"_id": ObjectId(key_id), "tenant_id": tenant_id},
            {"$set": {"is_revoked": True}},
        )

        if result.matched_count == 0:
            return False

        logger.info(
            "api_key_revoked",
            extra={"key_id": key_id, "tenant_id": tenant_id},
        )
        return True
```

- [ ] **Step 4: Run all service tests**

Run: `cd apps/api && uv run pytest tests/test_api_key_service.py -v`
Expected: 9 tests PASS

- [ ] **Step 5: Commit**

```
git add apps/api/src/services/api_key.py apps/api/tests/test_api_key_service.py
git commit -m "feat(api): add API key listing and revocation"
```

---

### Task 5: Keys Router

**Files:**
- Create: `apps/api/src/routers/keys.py`
- Create: `apps/api/tests/test_api_key_router.py`
- Modify: `apps/api/src/main.py`
- Modify: `apps/api/tests/conftest.py`

- [ ] **Step 1: Update conftest to add api_keys_collection mock**

In `apps/api/tests/conftest.py`, add `api_keys_collection` to the `mock_deps` fixture. Add this line after `deps.conversations_collection = MagicMock()`:

```python
    deps.api_keys_collection = MagicMock()
```

- [ ] **Step 2: Write failing tests for keys router**

Create `apps/api/tests/test_api_key_router.py`:

```python
"""Tests for API keys router endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from tests.conftest import make_auth_header


@pytest.fixture
def keys_client(mock_deps):
    """Create test client with api_keys collection mock."""
    from src.main import app

    mock_deps.api_keys_collection = MagicMock()

    with TestClient(app) as c:
        app.state.deps = mock_deps
        yield c


@pytest.mark.unit
def test_create_key_success(keys_client):
    """POST /api/v1/keys returns 201 with raw key."""
    with patch("src.routers.keys.APIKeyService") as mock_service:
        instance = mock_service.return_value
        instance.create_key = AsyncMock(
            return_value={
                "raw_key": "mrag_7kB2xR9mQ4nLpW5vX8yZ1aB3cD6eF9gH0jK2mN4",
                "key_prefix": "7kB2xR9m",
                "name": "Production",
                "permissions": ["chat", "search"],
                "created_at": datetime(2026, 4, 4, tzinfo=timezone.utc),
            }
        )

        response = keys_client.post(
            "/api/v1/keys",
            json={"name": "Production"},
            headers=make_auth_header(),
        )

    assert response.status_code == 201
    data = response.json()
    assert data["raw_key"].startswith("mrag_")
    assert data["key_prefix"] == "7kB2xR9m"
    assert data["name"] == "Production"


@pytest.mark.unit
def test_create_key_without_auth_returns_401(keys_client):
    """POST /api/v1/keys without auth returns 401."""
    response = keys_client.post(
        "/api/v1/keys",
        json={"name": "Test Key"},
    )
    assert response.status_code == 401


@pytest.mark.unit
def test_list_keys_success(keys_client):
    """GET /api/v1/keys returns key list for tenant."""
    key_id = str(ObjectId())
    with patch("src.routers.keys.APIKeyService") as mock_service:
        instance = mock_service.return_value
        instance.list_keys = AsyncMock(
            return_value=[
                {
                    "id": key_id,
                    "key_prefix": "7kB2xR9m",
                    "name": "Production",
                    "permissions": ["chat", "search"],
                    "is_revoked": False,
                    "last_used_at": None,
                    "created_at": datetime(2026, 4, 4, tzinfo=timezone.utc),
                }
            ]
        )

        response = keys_client.get(
            "/api/v1/keys",
            headers=make_auth_header(),
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data["keys"]) == 1
    assert data["keys"][0]["key_prefix"] == "7kB2xR9m"
    assert "key_hash" not in data["keys"][0]


@pytest.mark.unit
def test_list_keys_empty(keys_client):
    """GET /api/v1/keys returns empty list for tenant with no keys."""
    with patch("src.routers.keys.APIKeyService") as mock_service:
        instance = mock_service.return_value
        instance.list_keys = AsyncMock(return_value=[])

        response = keys_client.get(
            "/api/v1/keys",
            headers=make_auth_header(),
        )

    assert response.status_code == 200
    assert response.json()["keys"] == []


@pytest.mark.unit
def test_revoke_key_success(keys_client):
    """DELETE /api/v1/keys/{key_id} revokes the key."""
    key_id = str(ObjectId())
    with patch("src.routers.keys.APIKeyService") as mock_service:
        instance = mock_service.return_value
        instance.revoke_key = AsyncMock(return_value=True)

        response = keys_client.delete(
            f"/api/v1/keys/{key_id}",
            headers=make_auth_header(),
        )

    assert response.status_code == 200
    assert "revoked" in response.json()["message"].lower()


@pytest.mark.unit
def test_revoke_key_not_found(keys_client):
    """DELETE /api/v1/keys/{key_id} returns 404 for wrong tenant or missing key."""
    key_id = str(ObjectId())
    with patch("src.routers.keys.APIKeyService") as mock_service:
        instance = mock_service.return_value
        instance.revoke_key = AsyncMock(return_value=False)

        response = keys_client.delete(
            f"/api/v1/keys/{key_id}",
            headers=make_auth_header(),
        )

    assert response.status_code == 404


@pytest.mark.unit
def test_revoke_key_invalid_id_format(keys_client):
    """DELETE /api/v1/keys/{key_id} returns 400 for invalid ObjectId."""
    with patch("src.routers.keys.APIKeyService") as mock_service:
        instance = mock_service.return_value
        instance.revoke_key = AsyncMock(side_effect=Exception("invalid ObjectId"))

        response = keys_client.delete(
            "/api/v1/keys/not-a-valid-id",
            headers=make_auth_header(),
        )

    assert response.status_code == 400
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd apps/api && uv run pytest tests/test_api_key_router.py -v`
Expected: FAIL — router not found, 404 on all endpoints

- [ ] **Step 4: Implement keys router**

Create `apps/api/src/routers/keys.py`:

```python
"""API key management endpoints."""

import logging

from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException

from src.core.dependencies import AgentDependencies
from src.core.deps import get_deps
from src.core.tenant import get_tenant_id
from src.models.api import (
    CreateKeyRequest,
    CreateKeyResponse,
    KeyListResponse,
    KeyResponse,
    MessageResponse,
)
from src.services.api_key import APIKeyService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/keys", tags=["api-keys"])


def _get_api_key_service(deps: AgentDependencies = Depends(get_deps)) -> APIKeyService:
    """Create APIKeyService with injected collection."""
    return APIKeyService(api_keys_collection=deps.api_keys_collection)


@router.post("", response_model=CreateKeyResponse, status_code=201)
async def create_key(
    body: CreateKeyRequest,
    tenant_id: str = Depends(get_tenant_id),
    service: APIKeyService = Depends(_get_api_key_service),
):
    """Generate a new API key. The raw key is returned once and cannot be retrieved again."""
    result = await service.create_key(
        tenant_id=tenant_id,
        name=body.name,
        permissions=body.permissions,
    )
    return CreateKeyResponse(**result)


@router.get("", response_model=KeyListResponse)
async def list_keys(
    tenant_id: str = Depends(get_tenant_id),
    service: APIKeyService = Depends(_get_api_key_service),
):
    """List all API keys for the authenticated tenant."""
    keys = await service.list_keys(tenant_id)
    return KeyListResponse(keys=[KeyResponse(**k) for k in keys])


@router.delete("/{key_id}", response_model=MessageResponse)
async def revoke_key(
    key_id: str,
    tenant_id: str = Depends(get_tenant_id),
    service: APIKeyService = Depends(_get_api_key_service),
):
    """Revoke an API key (soft delete)."""
    try:
        revoked = await service.revoke_key(key_id=key_id, tenant_id=tenant_id)
    except (InvalidId, Exception):
        raise HTTPException(status_code=400, detail="Invalid key ID format")

    if not revoked:
        raise HTTPException(status_code=404, detail="API key not found")

    return MessageResponse(message="API key revoked")
```

- [ ] **Step 5: Register the router in main.py**

In `apps/api/src/main.py`, add the import and include_router:

Add after `from src.routers.auth import router as auth_router`:
```python
from src.routers.keys import router as keys_router
```

Add after `app.include_router(auth_router)`:
```python
app.include_router(keys_router)
```

- [ ] **Step 6: Run router tests**

Run: `cd apps/api && uv run pytest tests/test_api_key_router.py -v`
Expected: 7 tests PASS

- [ ] **Step 7: Run all existing tests to check for regressions**

Run: `cd apps/api && uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```
git add apps/api/src/routers/keys.py apps/api/tests/test_api_key_router.py apps/api/src/main.py apps/api/tests/conftest.py
git commit -m "feat(api): add /api/v1/keys CRUD router and tests"
```

---

### Task 6: Update Tenant Middleware for API Key Auth

**Files:**
- Modify: `apps/api/src/core/tenant.py`
- Modify: `apps/api/tests/test_tenant.py`

- [ ] **Step 1: Write failing tests for API key auth in tenant middleware**

Replace the entire contents of `apps/api/tests/test_tenant.py` with:

```python
"""Tests for tenant dependency (JWT + API key auth)."""

import hashlib
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from tests.conftest import JWT_SECRET, MOCK_TENANT_ID


def _create_tenant_app():
    """Create a test app with tenant extraction."""
    from src.core.deps import get_deps
    from src.core.tenant import get_tenant_id

    app = FastAPI()

    @app.get("/test")
    async def test_endpoint(tenant_id: str = Depends(get_tenant_id)):
        return {"tenant_id": tenant_id}

    return app


@pytest.fixture
def tenant_app():
    """Create test client for JWT-only tests (no deps needed for JWT path)."""
    app = _create_tenant_app()
    # Set up mock deps on app.state so get_deps works
    mock_deps = MagicMock()
    mock_deps.api_keys_collection = MagicMock()
    mock_deps.api_keys_collection.find_one = AsyncMock(return_value=None)
    app.state.deps = mock_deps
    return TestClient(app)


@pytest.fixture
def api_key_app():
    """Create test client with mock api_keys collection for API key tests."""
    app = _create_tenant_app()
    mock_deps = MagicMock()
    mock_api_keys = MagicMock()
    mock_api_keys.find_one = AsyncMock(return_value=None)
    mock_api_keys.update_one = AsyncMock()
    mock_deps.api_keys_collection = mock_api_keys
    app.state.deps = mock_deps
    return TestClient(app), mock_api_keys


# --- JWT tests (unchanged behavior) ---


@pytest.mark.unit
def test_missing_auth_header_returns_401(tenant_app):
    """Request without Authorization header returns 401."""
    response = tenant_app.get("/test")
    assert response.status_code == 401
    assert "Authorization" in response.json()["detail"]


@pytest.mark.unit
def test_valid_jwt_returns_tenant_id(tenant_app):
    """Request with valid JWT extracts tenant_id."""
    token = jwt.encode(
        {"sub": "user-1", "tenant_id": MOCK_TENANT_ID, "role": "owner"},
        JWT_SECRET,
        algorithm="HS256",
    )
    response = tenant_app.get("/test", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["tenant_id"] == MOCK_TENANT_ID


@pytest.mark.unit
def test_invalid_jwt_returns_401(tenant_app):
    """Request with invalid JWT returns 401."""
    response = tenant_app.get("/test", headers={"Authorization": "Bearer bad-token"})
    assert response.status_code == 401


# --- API key tests ---


@pytest.mark.unit
def test_valid_api_key_returns_tenant_id(api_key_app):
    """Request with valid mrag_ API key extracts tenant_id."""
    client, mock_api_keys = api_key_app
    raw_key = "mrag_7kB2xR9mQ4nLpW5vX8yZ1aB3cD6eF9gH0jK2mN4"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    mock_api_keys.find_one.return_value = {
        "_id": "key-id-123",
        "tenant_id": "tenant-from-key",
        "key_hash": key_hash,
        "permissions": ["chat", "search"],
        "is_revoked": False,
    }

    response = client.get("/test", headers={"Authorization": f"Bearer {raw_key}"})
    assert response.status_code == 200
    assert response.json()["tenant_id"] == "tenant-from-key"

    # Verify last_used_at was updated
    mock_api_keys.update_one.assert_called_once()


@pytest.mark.unit
def test_revoked_api_key_returns_401(api_key_app):
    """Request with revoked API key returns 401."""
    client, mock_api_keys = api_key_app
    raw_key = "mrag_revokedkey12345678901234567890123"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    mock_api_keys.find_one.return_value = {
        "_id": "key-id-123",
        "tenant_id": "tenant-abc",
        "key_hash": key_hash,
        "permissions": ["chat"],
        "is_revoked": True,
    }

    response = client.get("/test", headers={"Authorization": f"Bearer {raw_key}"})
    assert response.status_code == 401
    assert "revoked" in response.json()["detail"].lower()


@pytest.mark.unit
def test_unknown_api_key_returns_401(api_key_app):
    """Request with unknown mrag_ key returns 401."""
    client, mock_api_keys = api_key_app
    mock_api_keys.find_one.return_value = None

    response = client.get(
        "/test", headers={"Authorization": "Bearer mrag_unknownkey123456789012345678"}
    )
    assert response.status_code == 401
    assert "Invalid API key" in response.json()["detail"]
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `cd apps/api && uv run pytest tests/test_tenant.py::test_valid_api_key_returns_tenant_id -v`
Expected: FAIL — current `get_tenant_id()` tries to decode `mrag_...` as JWT and returns 401 with wrong message

- [ ] **Step 3: Update `get_tenant_id()` to support API key auth**

Replace the entire contents of `apps/api/src/core/tenant.py` with:

```python
"""Tenant extraction from JWT or API key."""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, Header, HTTPException

from src.core.dependencies import AgentDependencies
from src.core.deps import get_deps
from src.core.security import decode_jwt
from src.core.settings import load_settings

logger = logging.getLogger(__name__)

_API_KEY_PREFIX = "mrag_"


async def get_tenant_id(
    authorization: Optional[str] = Header(default=None),
    deps: AgentDependencies = Depends(get_deps),
) -> str:
    """Extract tenant_id from JWT or API key in the Authorization header.

    Detects auth method by the 'mrag_' prefix:
    - 'mrag_...' → API key path (hash and look up in api_keys collection)
    - Otherwise → JWT path (decode with nextauth_secret)

    Args:
        authorization: Authorization header value.
        deps: Application dependencies for DB access.

    Returns:
        Validated tenant_id string.

    Raises:
        HTTPException: 401 if token is missing, invalid, or lacks tenant_id.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authorization header with Bearer token is required",
        )

    token = authorization[7:]  # Strip "Bearer "

    if token.startswith(_API_KEY_PREFIX):
        return await _resolve_api_key(token, deps)

    return _resolve_jwt(token)


async def _resolve_api_key(raw_key: str, deps: AgentDependencies) -> str:
    """Validate an API key and return its tenant_id.

    Args:
        raw_key: The full API key string (mrag_...).
        deps: Application dependencies for DB access.

    Returns:
        tenant_id from the API key document.

    Raises:
        HTTPException: 401 if key is invalid or revoked.
    """
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    doc = await deps.api_keys_collection.find_one({"key_hash": key_hash})

    if not doc:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if doc.get("is_revoked", False):
        raise HTTPException(status_code=401, detail="API key has been revoked")

    # Fire-and-forget: update last_used_at (don't await in request path)
    await deps.api_keys_collection.update_one(
        {"key_hash": key_hash},
        {"$set": {"last_used_at": datetime.now(timezone.utc)}},
    )

    return doc["tenant_id"]


def _resolve_jwt(token: str) -> str:
    """Validate a JWT and return its tenant_id.

    Args:
        token: JWT token string.

    Returns:
        tenant_id from the JWT payload.

    Raises:
        HTTPException: 401 if token is invalid or lacks tenant_id.
    """
    settings = load_settings()
    payload = decode_jwt(token, settings.nextauth_secret)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Token missing tenant_id claim")

    return tenant_id
```

- [ ] **Step 4: Run tenant tests**

Run: `cd apps/api && uv run pytest tests/test_tenant.py -v`
Expected: 6 tests PASS

- [ ] **Step 5: Run all tests to check for regressions**

Run: `cd apps/api && uv run pytest -v`
Expected: All tests PASS. Note: existing tests that use `get_tenant_id` via `Depends` will now also inject `deps` — this is fine because `get_deps` pulls from `app.state.deps` which is mocked in conftest.

- [ ] **Step 6: Commit**

```
git add apps/api/src/core/tenant.py apps/api/tests/test_tenant.py
git commit -m "feat(api): extend tenant middleware to support API key auth"
```

---

### Task 7: Lint, Full Test Suite, and Final Verification

**Files:** All modified files

- [ ] **Step 1: Run ruff lint**

Run: `cd apps/api && uv run ruff check .`
Expected: No errors. If errors found, fix them.

- [ ] **Step 2: Run ruff format check**

Run: `cd apps/api && uv run ruff format --check .`
Expected: No formatting issues. If issues found, run `uv run ruff format .` to fix.

- [ ] **Step 3: Run full test suite**

Run: `cd apps/api && uv run pytest -v`
Expected: All tests PASS (existing + new).

- [ ] **Step 4: Verify imports are clean**

Run: `cd apps/api && uv run python -c "from src.services.api_key import APIKeyService; from src.routers.keys import router; from src.core.tenant import get_tenant_id; print('All imports OK')"`
Expected: `All imports OK`

- [ ] **Step 5: Commit any lint fixes**

If any lint fixes were needed:
```
git add -A
git commit -m "fix: resolve lint issues in API key implementation"
```

---

### Task 8: Create Feature Branch and PR

- [ ] **Step 1: Create feature branch from the commits**

All work so far was done on a working branch. Use `/commit-push-pr` to push and create the PR linking to issue #8.

PR title: `feat: add API key generation, validation, and management`
PR body should reference `Closes #8` and summarize the changes.
