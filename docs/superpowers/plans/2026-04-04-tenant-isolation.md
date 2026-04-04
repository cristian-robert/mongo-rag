# Tenant Isolation Hardening — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all tenant isolation gaps and add a safety net middleware so no future endpoint can accidentally leak cross-tenant data.

**Architecture:** Surgical fixes to 4 identified gaps (WebSocket auth, email uniqueness, reset token scoping, tenant guard middleware) plus comprehensive negative tests. Keeps the existing explicit `get_tenant_id()` dependency injection pattern — no repository abstraction.

**Tech Stack:** FastAPI, Motor (async MongoDB), pytest + pytest-asyncio, python-jose (JWT)

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/core/database.py` | Create | Index management — `ensure_indexes()` called on startup |
| `src/core/middleware.py` | Create | `TenantGuardMiddleware` — safety net for missing tenant context |
| `src/core/tenant.py` | Modify | Set `request.state.tenant_id` in auth deps; extract helpers for WS reuse |
| `src/main.py` | Modify | Register middleware, call `ensure_indexes()` on startup |
| `src/models/user.py` | Modify | Add `tenant_id` to `PasswordResetTokenModel` |
| `src/services/auth.py` | Modify | Scope reset tokens with `tenant_id` |
| `src/routers/chat.py` | Modify | Rewrite WebSocket auth (JWT/API key from `token` query param) |
| `tests/test_tenant_isolation.py` | Create | Cross-tenant negative tests |
| `tests/test_tenant_guard.py` | Create | Middleware unit tests |
| `tests/conftest.py` | Modify | Add `TENANT_B` fixtures |

---

### Task 1: Database Index Management

**Files:**
- Create: `apps/api/src/core/database.py`
- Modify: `apps/api/src/main.py:19-36`
- Test: `apps/api/tests/test_database_indexes.py`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_database_indexes.py`:

```python
"""Tests for database index creation."""

from unittest.mock import AsyncMock, MagicMock, call

import pytest


@pytest.mark.unit
async def test_ensure_indexes_creates_expected_indexes():
    """ensure_indexes creates all required indexes on startup."""
    from src.core.database import ensure_indexes

    mock_db = MagicMock()
    collections = {}
    for name in [
        "users", "documents", "chunks", "conversations",
        "api_keys", "password_reset_tokens",
    ]:
        mock_col = MagicMock()
        mock_col.create_index = AsyncMock()
        collections[name] = mock_col

    mock_db.__getitem__ = MagicMock(side_effect=lambda name: collections[name])

    await ensure_indexes(mock_db)

    # users: unique email index
    collections["users"].create_index.assert_any_call(
        "email", unique=True, background=True
    )

    # documents: tenant + created_at compound
    collections["documents"].create_index.assert_any_call(
        [("tenant_id", 1), ("created_at", -1)], background=True
    )

    # chunks: tenant + document_id compound
    collections["chunks"].create_index.assert_any_call(
        [("tenant_id", 1), ("document_id", 1)], background=True
    )

    # conversations: tenant + created_at compound
    collections["conversations"].create_index.assert_any_call(
        [("tenant_id", 1), ("created_at", -1)], background=True
    )

    # api_keys: tenant_id
    collections["api_keys"].create_index.assert_any_call(
        "tenant_id", background=True
    )

    # reset_tokens: token_hash
    collections["password_reset_tokens"].create_index.assert_any_call(
        "token_hash", background=True
    )

    # reset_tokens: TTL on expires_at (24 hours)
    collections["password_reset_tokens"].create_index.assert_any_call(
        "expires_at", expireAfterSeconds=86400, background=True
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_database_indexes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.core.database'`

- [ ] **Step 3: Write the implementation**

Create `apps/api/src/core/database.py`:

```python
"""Database index management."""

import logging

from pymongo.asynchronous.database import AsyncDatabase

logger = logging.getLogger(__name__)


async def ensure_indexes(db: AsyncDatabase) -> None:
    """Create required indexes on all collections.

    Safe to call on every startup — create_index is idempotent.

    Args:
        db: The async MongoDB database instance.
    """
    logger.info("ensuring_database_indexes")

    # Users: unique email for global email uniqueness
    await db["users"].create_index("email", unique=True, background=True)

    # Documents: tenant-scoped listing
    await db["documents"].create_index(
        [("tenant_id", 1), ("created_at", -1)], background=True
    )

    # Chunks: tenant-scoped lookups by document
    await db["chunks"].create_index(
        [("tenant_id", 1), ("document_id", 1)], background=True
    )

    # Conversations: tenant-scoped listing
    await db["conversations"].create_index(
        [("tenant_id", 1), ("created_at", -1)], background=True
    )

    # API keys: tenant-scoped listing
    await db["api_keys"].create_index("tenant_id", background=True)

    # Reset tokens: hash lookup
    await db["password_reset_tokens"].create_index("token_hash", background=True)

    # Reset tokens: auto-cleanup after 24 hours
    await db["password_reset_tokens"].create_index(
        "expires_at", expireAfterSeconds=86400, background=True
    )

    logger.info("database_indexes_ensured")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_database_indexes.py -v`
Expected: PASS

- [ ] **Step 5: Wire into app startup**

Modify `apps/api/src/main.py`. Add import and call `ensure_indexes` inside the lifespan after `deps.initialize()`:

```python
# Add import at top:
from src.core.database import ensure_indexes

# Inside lifespan, after deps.initialize() succeeds (after line 29):
        await ensure_indexes(deps.db)
```

- [ ] **Step 6: Commit**

```
feat: add database index management with tenant isolation indexes

Closes step 1 of #9. Creates ensure_indexes() called on startup.
Adds unique email index, tenant compound indexes, and reset token TTL.
```

---

### Task 2: Add `tenant_id` to Password Reset Token Model

**Files:**
- Modify: `apps/api/src/models/user.py:48-55`
- Modify: `apps/api/src/services/auth.py:170-176` (token creation)
- Modify: `apps/api/src/services/auth.py:199-206` (token validation)
- Test: `apps/api/tests/test_auth_service.py` (existing — add cases)

- [ ] **Step 1: Write the failing test**

Add to `apps/api/tests/test_auth_service.py`:

```python
@pytest.mark.unit
async def test_reset_token_includes_tenant_id():
    """create_password_reset_token stores tenant_id from user doc."""
    users_col = MagicMock()
    tenants_col = MagicMock()
    reset_tokens_col = MagicMock()

    users_col.find_one = AsyncMock(return_value={
        "_id": ObjectId(),
        "email": "alice@example.com",
        "tenant_id": "tenant-abc",
    })
    reset_tokens_col.update_many = AsyncMock()
    reset_tokens_col.insert_one = AsyncMock()

    service = AuthService(users_col, tenants_col, reset_tokens_col)
    await service.create_password_reset_token("alice@example.com")

    inserted_doc = reset_tokens_col.insert_one.call_args[0][0]
    assert inserted_doc["tenant_id"] == "tenant-abc"


@pytest.mark.unit
async def test_reset_password_validates_tenant_id():
    """reset_password verifies token tenant_id matches user tenant_id."""
    users_col = MagicMock()
    tenants_col = MagicMock()
    reset_tokens_col = MagicMock()

    reset_tokens_col.find_one_and_update = AsyncMock(return_value={
        "user_id": str(ObjectId()),
        "tenant_id": "tenant-abc",
        "token_hash": "abc123",
    })

    # User belongs to a DIFFERENT tenant
    users_col.find_one = AsyncMock(return_value={
        "_id": ObjectId(reset_tokens_col.find_one_and_update.return_value["user_id"]),
        "tenant_id": "tenant-xyz",
    })
    users_col.update_one = AsyncMock(return_value=MagicMock(matched_count=1))

    service = AuthService(users_col, tenants_col, reset_tokens_col)
    with pytest.raises(ValueError, match="Invalid or expired reset token"):
        await service.reset_password("some-token", "new-password")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_auth_service.py::test_reset_token_includes_tenant_id tests/test_auth_service.py::test_reset_password_validates_tenant_id -v`
Expected: FAIL — `tenant_id` not in inserted doc / no tenant validation in reset

- [ ] **Step 3: Update the model**

Modify `apps/api/src/models/user.py`. Add `tenant_id` field to `PasswordResetTokenModel`:

```python
class PasswordResetTokenModel(BaseModel):
    """A password reset token (stored as SHA256 hash)."""

    user_id: str = Field(..., description="User this token belongs to")
    tenant_id: str = Field(..., description="Tenant this token belongs to")
    token_hash: str = Field(..., description="SHA256 hash of the reset token")
    expires_at: datetime = Field(..., description="Token expiry time")
    used: bool = Field(default=False, description="Whether the token has been consumed")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 4: Update `create_password_reset_token` in auth service**

Modify `apps/api/src/services/auth.py`, the `create_password_reset_token` method. Add `tenant_id` to the token document:

```python
    async def create_password_reset_token(self, email: str) -> Optional[str]:
        """Generate a password reset token for the given email.

        Returns None if the email is not found (prevents email enumeration).

        Args:
            email: User email.

        Returns:
            Raw token string, or None if email not found.
        """
        user = await self._users.find_one({"email": email.lower()})
        if not user:
            return None

        user_id = str(user["_id"])
        tenant_id = user["tenant_id"]

        # Invalidate any existing tokens for this user
        await self._reset_tokens.update_many(
            {"user_id": user_id, "used": False},
            {"$set": {"used": True}},
        )

        # Generate new token
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        now = datetime.now(timezone.utc)

        token_doc = {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "token_hash": token_hash,
            "expires_at": now + timedelta(hours=1),
            "used": False,
            "created_at": now,
        }
        await self._reset_tokens.insert_one(token_doc)

        logger.info("password_reset_token_created", extra={"user_id": user_id})
        return raw_token
```

- [ ] **Step 5: Update `reset_password` with tenant validation**

Modify `apps/api/src/services/auth.py`, the `reset_password` method. After claiming the token, verify tenant_id matches the user:

```python
    async def reset_password(self, token: str, new_password: str) -> None:
        """Reset a user's password using a reset token.

        Uses atomic find_one_and_update to claim the token, preventing
        concurrent use of the same token. Validates tenant_id matches
        the user for defense in depth.

        Args:
            token: Raw reset token from the email link.
            new_password: New plaintext password.

        Raises:
            ValueError: If token is invalid, expired, or already used.
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        now = datetime.now(timezone.utc)

        # Atomically claim the token: find unused + unexpired, mark used in one op
        token_doc = await self._reset_tokens.find_one_and_update(
            {
                "token_hash": token_hash,
                "used": False,
                "expires_at": {"$gt": now},
            },
            {"$set": {"used": True}},
        )

        if not token_doc:
            raise ValueError("Invalid or expired reset token")

        # Defense in depth: verify token tenant matches user tenant
        user = await self._users.find_one({"_id": ObjectId(token_doc["user_id"])})
        if not user or user.get("tenant_id") != token_doc.get("tenant_id"):
            logger.error(
                "password_reset_tenant_mismatch",
                extra={
                    "user_id": token_doc["user_id"],
                    "token_tenant": token_doc.get("tenant_id"),
                    "user_tenant": user.get("tenant_id") if user else None,
                },
            )
            raise ValueError("Invalid or expired reset token")

        # Update the user's password
        new_hash = hash_password(new_password)
        result = await self._users.update_one(
            {"_id": ObjectId(token_doc["user_id"])},
            {"$set": {"hashed_password": new_hash, "updated_at": now}},
        )

        if result.matched_count == 0:
            logger.error(
                "password_reset_user_not_found",
                extra={"user_id": token_doc["user_id"]},
            )
            raise ValueError("User account not found")

        logger.info("password_reset_completed", extra={"user_id": token_doc["user_id"]})
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd apps/api && uv run pytest tests/test_auth_service.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```
feat: scope password reset tokens to tenant_id

Adds tenant_id field to PasswordResetTokenModel and validates it during
password reset for defense in depth.
```

---

### Task 3: WebSocket Authentication

**Files:**
- Modify: `apps/api/src/routers/chat.py:76-139`
- Modify: `apps/api/src/core/tenant.py` (expose resolution helpers)
- Test: `apps/api/tests/test_chat_router.py` (add WS auth tests)

- [ ] **Step 1: Write the failing tests**

Add to `apps/api/tests/test_chat_router.py`:

```python
from conftest import JWT_SECRET, MOCK_TENANT_ID
from jose import jwt


def _make_ws_token(tenant_id: str = MOCK_TENANT_ID) -> str:
    """Create a JWT token for WebSocket auth."""
    return jwt.encode(
        {"sub": "test-user", "tenant_id": tenant_id, "role": "owner"},
        JWT_SECRET,
        algorithm="HS256",
    )


def test_websocket_rejects_missing_token(client):
    """WebSocket without token query param is rejected."""
    with pytest.raises(Exception):
        with client.websocket_connect("/api/v1/chat/ws"):
            pass


def test_websocket_rejects_invalid_token(client):
    """WebSocket with invalid token is rejected."""
    with pytest.raises(Exception):
        with client.websocket_connect("/api/v1/chat/ws?token=invalid-jwt"):
            pass


def test_websocket_rejects_no_tenant_in_token(client):
    """WebSocket with JWT missing tenant_id claim is rejected."""
    token = jwt.encode({"sub": "test-user"}, JWT_SECRET, algorithm="HS256")
    with pytest.raises(Exception):
        with client.websocket_connect(f"/api/v1/chat/ws?token={token}"):
            pass


def test_websocket_accepts_valid_jwt(client, mock_deps):
    """WebSocket with valid JWT token is accepted."""
    token = _make_ws_token()
    # Mock the chat service to avoid real DB calls
    mock_deps.settings = MagicMock()

    with client.websocket_connect(f"/api/v1/chat/ws?token={token}") as ws:
        # Connection accepted — send a cancel to cleanly close
        ws.send_json({"type": "cancel"})
        response = ws.receive_json()
        assert response["type"] == "cancelled"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && uv run pytest tests/test_chat_router.py::test_websocket_rejects_missing_token tests/test_chat_router.py::test_websocket_accepts_valid_jwt -v`
Expected: FAIL — current WS accepts any `tenant_id` param, doesn't use `token`

- [ ] **Step 3: Expose auth resolution functions for WebSocket use**

Modify `apps/api/src/core/tenant.py`. Make `_resolve_api_key` and `_resolve_jwt` importable by renaming to public functions (keeping underscore-prefixed aliases for backward compat is unnecessary — no external consumers):

Add a new async function for WebSocket auth that doesn't depend on FastAPI's `Depends`:

```python
async def resolve_token(raw_token: str, deps: AgentDependencies) -> str:
    """Resolve a raw token (JWT or API key) to a tenant_id.

    Used by WebSocket handlers where FastAPI Depends is not available.

    Args:
        raw_token: JWT or API key string (without 'Bearer ' prefix).
        deps: Application dependencies for DB access.

    Returns:
        Validated tenant_id string.

    Raises:
        HTTPException: 401 if token is invalid.
    """
    if raw_token.startswith(_API_KEY_PREFIX):
        return await _resolve_api_key(raw_token, deps)
    return _resolve_jwt(raw_token)
```

- [ ] **Step 4: Rewrite WebSocket handler**

Modify `apps/api/src/routers/chat.py`. Replace the WebSocket handler (lines 76-139):

```python
@router.websocket("/chat/ws")
async def chat_websocket(
    websocket: WebSocket,
    token: Optional[str] = None,
):
    """WebSocket endpoint for real-time chat.

    Authenticate via query parameter: /api/v1/chat/ws?token=<jwt_or_api_key>
    """
    if not token or not token.strip():
        await websocket.close(code=4001, reason="token query parameter required")
        return

    # Resolve tenant from token before accepting connection
    deps: AgentDependencies = websocket.app.state.deps
    try:
        tenant_id = await resolve_token(token.strip(), deps)
    except HTTPException:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    await websocket.accept()
    service = ChatService(deps)

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                data = json.loads(raw)
                msg = WSMessage(**data)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue
            except (ValueError, TypeError) as e:
                logger.warning("WebSocket invalid message: %s", str(e))
                await websocket.send_json({"type": "error", "message": "Invalid message format"})
                continue

            if msg.type == "cancel":
                await websocket.send_json({"type": "cancelled"})
                continue

            if msg.type == "message" and msg.content:
                try:
                    async for event in service.handle_message_stream(
                        message=msg.content,
                        tenant_id=tenant_id,
                        conversation_id=msg.conversation_id,
                    ):
                        await websocket.send_json(event)
                except Exception as e:
                    logger.exception("WebSocket chat error: %s", str(e))
                    await websocket.send_json(
                        {"type": "error", "message": "An internal error occurred"}
                    )
            else:
                await websocket.send_json(
                    {"type": "error", "message": "Expected type 'message' with content"}
                )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: tenant=%s", tenant_id)
    except Exception as e:
        logger.exception("WebSocket error: %s", str(e))
        try:
            await websocket.close(code=1011, reason="Internal error")
        except Exception:
            pass
```

Update the imports at the top of `chat.py`:

```python
from src.core.tenant import get_tenant_id, resolve_token
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd apps/api && uv run pytest tests/test_chat_router.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```
fix(security): authenticate WebSocket with JWT/API key token

Replaces raw tenant_id query param with token-based auth.
Client sends JWT or API key as ?token= param, server validates
before accepting the connection.

Closes the critical WebSocket isolation bypass in #9.
```

---

### Task 4: Tenant Guard Middleware

**Files:**
- Create: `apps/api/src/core/middleware.py`
- Modify: `apps/api/src/core/tenant.py:20-51` (set `request.state.tenant_id`)
- Modify: `apps/api/src/main.py` (register middleware)
- Test: `apps/api/tests/test_tenant_guard.py`

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_tenant_guard.py`:

```python
"""Tests for TenantGuardMiddleware."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from src.core.middleware import TenantGuardMiddleware


def _create_app(*, debug: bool = False) -> FastAPI:
    """Create a minimal FastAPI app with the tenant guard middleware."""
    app = FastAPI(debug=debug)
    app.add_middleware(TenantGuardMiddleware)

    @app.get("/api/v1/protected")
    async def protected(request: Request):
        # Simulate a handler that FORGETS to set tenant context
        return {"ok": True}

    @app.get("/api/v1/safe")
    async def safe(request: Request):
        request.state.tenant_id = "tenant-abc"
        return {"ok": True}

    @app.get("/api/v1/auth/login")
    async def login():
        return {"ok": True}

    @app.get("/health")
    async def health():
        return {"ok": True}

    return app


@pytest.mark.unit
def test_guard_warns_on_missing_tenant_context(caplog):
    """Middleware logs warning when protected route lacks tenant context."""
    app = _create_app(debug=False)
    client = TestClient(app)

    with caplog.at_level(logging.WARNING):
        response = client.get("/api/v1/protected")

    assert response.status_code == 200  # Never blocks in prod
    assert any("tenant_id not set" in r.message for r in caplog.records)


@pytest.mark.unit
def test_guard_silent_when_tenant_set():
    """Middleware stays silent when tenant context is set."""
    app = _create_app(debug=False)
    client = TestClient(app)

    with pytest.raises(AssertionError):
        # Should NOT find any warning
        response = client.get("/api/v1/safe")
        assert response.status_code == 200


@pytest.mark.unit
def test_guard_skips_auth_routes(caplog):
    """Middleware does not check auth routes."""
    app = _create_app(debug=False)
    client = TestClient(app)

    with caplog.at_level(logging.WARNING):
        response = client.get("/api/v1/auth/login")

    assert response.status_code == 200
    assert not any("tenant_id not set" in r.message for r in caplog.records)


@pytest.mark.unit
def test_guard_skips_health(caplog):
    """Middleware does not check health endpoint."""
    app = _create_app(debug=False)
    client = TestClient(app)

    with caplog.at_level(logging.WARNING):
        response = client.get("/health")

    assert response.status_code == 200
    assert not any("tenant_id not set" in r.message for r in caplog.records)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && uv run pytest tests/test_tenant_guard.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.core.middleware'`

- [ ] **Step 3: Write the middleware**

Create `apps/api/src/core/middleware.py`:

```python
"""Tenant guard middleware — safety net for missing tenant context."""

import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Routes exempt from tenant guard checks
_EXEMPT_PREFIXES = (
    "/api/v1/auth",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
)


class TenantGuardMiddleware(BaseHTTPMiddleware):
    """Log a warning if a protected route completes without tenant context.

    This is a safety net, not primary enforcement. Primary enforcement
    is the get_tenant_id() dependency injected into route handlers.

    In production: logs a warning (never blocks).
    In debug mode: logs a warning (never blocks — avoidance of false
    positives on routes that legitimately don't need tenant context).
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Initialize tenant_id state so hasattr checks work
        request.state.tenant_id = None

        response = await call_next(request)

        path = request.url.path

        # Skip exempt routes
        if any(path.startswith(prefix) for prefix in _EXEMPT_PREFIXES):
            return response

        # Only check /api/v1/ routes
        if not path.startswith("/api/v1/"):
            return response

        # Check if tenant context was set
        tenant_id = getattr(request.state, "tenant_id", None)
        if not tenant_id:
            logger.warning(
                "tenant_id not set for protected route",
                extra={"path": path, "method": request.method},
            )

        return response
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/api && uv run pytest tests/test_tenant_guard.py -v`
Expected: ALL PASS

- [ ] **Step 5: Update `get_tenant_id` to set `request.state.tenant_id`**

Modify `apps/api/src/core/tenant.py`. Update `get_tenant_id` to accept `Request` and set state:

```python
async def get_tenant_id(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    deps: AgentDependencies = Depends(get_deps),
) -> str:
    """Extract tenant_id from JWT or API key in the Authorization header.

    Also sets request.state.tenant_id for the TenantGuardMiddleware.

    Detects auth method by the 'mrag_' prefix:
    - 'mrag_...' → API key path (hash and look up in api_keys collection)
    - Otherwise → JWT path (decode with nextauth_secret)

    Args:
        request: FastAPI request (used to set tenant state).
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
        tenant_id = await _resolve_api_key(token, deps)
    else:
        tenant_id = _resolve_jwt(token)

    request.state.tenant_id = tenant_id
    return tenant_id
```

Update `get_tenant_id_from_jwt` similarly:

```python
async def get_tenant_id_from_jwt(
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> str:
    """Extract tenant_id from JWT only. Rejects API keys.

    Also sets request.state.tenant_id for the TenantGuardMiddleware.

    Args:
        request: FastAPI request (used to set tenant state).
        authorization: Authorization header value.

    Returns:
        Validated tenant_id string.

    Raises:
        HTTPException: 401 if token is missing, invalid, or an API key.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authorization header with Bearer token is required",
        )

    token = authorization[7:]  # Strip "Bearer "

    if token.startswith(_API_KEY_PREFIX):
        raise HTTPException(
            status_code=403,
            detail="API keys cannot access this endpoint",
        )

    tenant_id = _resolve_jwt(token)
    request.state.tenant_id = tenant_id
    return tenant_id
```

Add `Request` to the imports:

```python
from fastapi import Depends, Header, HTTPException, Request
```

- [ ] **Step 6: Register middleware in main.py**

Modify `apps/api/src/main.py`. Add import and register middleware after CORS:

```python
# Add import at top:
from src.core.middleware import TenantGuardMiddleware

# After the CORS middleware block (after line 53), add:
app.add_middleware(TenantGuardMiddleware)
```

- [ ] **Step 7: Run all tests to verify nothing broke**

Run: `cd apps/api && uv run pytest -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```
feat: add tenant guard middleware as safety net

Logs warnings when protected /api/v1/ routes complete without
tenant_id in request.state. Auth dependencies now set
request.state.tenant_id automatically.

Never blocks requests — observability only.
```

---

### Task 5: Cross-Tenant Negative Tests

**Files:**
- Modify: `apps/api/tests/conftest.py`
- Create: `apps/api/tests/test_tenant_isolation.py`

- [ ] **Step 1: Add Tenant B fixtures to conftest**

Modify `apps/api/tests/conftest.py`. Add second tenant constant and helper:

```python
MOCK_TENANT_B_ID = "test-tenant-002"


def make_auth_header_b(tenant_id: str = MOCK_TENANT_B_ID) -> dict:
    """Create Authorization header for Tenant B."""
    token = jwt.encode(
        {"sub": "test-user-b", "tenant_id": tenant_id, "role": "owner"},
        JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}
```

- [ ] **Step 2: Write cross-tenant isolation tests**

Create `apps/api/tests/test_tenant_isolation.py`:

```python
"""Cross-tenant isolation negative tests.

Verifies Tenant A cannot access Tenant B's data across all endpoints.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId
from jose import jwt

from conftest import (
    JWT_SECRET,
    MOCK_TENANT_ID,
    MOCK_TENANT_B_ID,
    make_auth_header,
    make_auth_header_b,
)


# ── Chat Isolation ──────────────────────────────────────────────────


@pytest.mark.unit
def test_chat_tenant_a_cannot_see_tenant_b_conversations(client, mock_deps):
    """Chat endpoint only queries with the authenticated tenant's ID."""
    captured_tenant_ids = []
    original_service = None

    class MockChatService:
        def __init__(self, deps):
            pass

        async def handle_message(self, *, message, tenant_id, conversation_id=None, search_type=None):
            captured_tenant_ids.append(tenant_id)
            return {
                "answer": "test",
                "sources": [],
                "conversation_id": "conv-1",
            }

    with patch("src.routers.chat.ChatService", MockChatService):
        response = client.post(
            "/api/v1/chat",
            json={"message": "hello"},
            headers=make_auth_header(),
        )

    assert response.status_code == 200
    assert captured_tenant_ids == [MOCK_TENANT_ID]
    assert MOCK_TENANT_B_ID not in captured_tenant_ids


# ── Document Isolation ──────────────────────────────────────────────


@pytest.mark.unit
def test_document_status_scoped_to_tenant(client, mock_deps):
    """Document status endpoint filters by authenticated tenant."""
    doc_id = str(ObjectId())
    mock_deps.documents_collection.find_one = AsyncMock(return_value=None)

    with patch("src.routers.ingest.IngestionService") as MockService:
        instance = MockService.return_value
        instance.get_document_status = AsyncMock(return_value=None)

        response = client.get(
            f"/api/v1/documents/{doc_id}/status",
            headers=make_auth_header(),
        )

    # Service should be called with tenant A's ID, not tenant B's
    call_args = instance.get_document_status.call_args
    if call_args:
        assert call_args.kwargs.get("tenant_id", call_args.args[1] if len(call_args.args) > 1 else None) == MOCK_TENANT_ID


# ── API Key Isolation ───────────────────────────────────────────────


@pytest.mark.unit
def test_list_keys_scoped_to_tenant(client, mock_deps):
    """List keys only returns keys for authenticated tenant."""
    tenant_a_key = {
        "_id": ObjectId(),
        "tenant_id": MOCK_TENANT_ID,
        "key_prefix": "mrag_abc",
        "name": "Key A",
        "permissions": ["chat"],
        "is_revoked": False,
        "last_used_at": None,
        "created_at": "2026-01-01T00:00:00Z",
    }

    with patch("src.routers.keys.APIKeyService") as MockService:
        instance = MockService.return_value
        instance.list_keys = AsyncMock(return_value=[tenant_a_key])

        response = client.get(
            "/api/v1/keys",
            headers=make_auth_header(),
        )

    assert response.status_code == 200
    # Service must have been called with tenant A's ID
    instance.list_keys.assert_called_once_with(MOCK_TENANT_ID)


@pytest.mark.unit
def test_revoke_key_scoped_to_tenant(client, mock_deps):
    """Revoke key only works for the authenticated tenant's keys."""
    key_id = str(ObjectId())

    with patch("src.routers.keys.APIKeyService") as MockService:
        instance = MockService.return_value
        instance.revoke_key = AsyncMock(return_value=True)

        response = client.delete(
            f"/api/v1/keys/{key_id}",
            headers=make_auth_header(),
        )

    # Service must have been called with tenant A's ID
    instance.revoke_key.assert_called_once_with(key_id, MOCK_TENANT_ID)


# ── Search Isolation ────────────────────────────────────────────────


@pytest.mark.unit
async def test_semantic_search_filters_by_tenant():
    """Semantic search pipeline includes tenant_id in $vectorSearch filter."""
    from src.services.search import semantic_search

    captured_pipelines = []
    mock_collection = MagicMock()

    async def capture_aggregate(pipeline):
        captured_pipelines.append(pipeline)

        class EmptyCursor:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise StopAsyncIteration

        return EmptyCursor()

    mock_collection.aggregate = capture_aggregate

    deps = MagicMock()
    deps.settings = MagicMock()
    deps.settings.default_match_count = 10
    deps.settings.max_match_count = 50
    deps.settings.mongodb_vector_index = "vector_index"
    deps.settings.mongodb_collection_documents = "documents"
    deps.settings.mongodb_collection_chunks = "chunks"
    deps.get_embedding = AsyncMock(return_value=[0.1] * 1536)
    deps.db = MagicMock()
    deps.db.__getitem__ = MagicMock(return_value=mock_collection)

    # Search as Tenant A
    await semantic_search(deps, "test query", tenant_id=MOCK_TENANT_ID)

    pipeline = captured_pipelines[0]
    vector_filter = pipeline[0]["$vectorSearch"]["filter"]
    assert vector_filter == {"tenant_id": MOCK_TENANT_ID}
    # Tenant B's ID must NOT appear
    assert MOCK_TENANT_B_ID not in str(pipeline)


@pytest.mark.unit
async def test_text_search_filters_by_tenant():
    """Text search pipeline includes tenant_id in $search compound filter."""
    from src.services.search import text_search

    captured_pipelines = []
    mock_collection = MagicMock()

    async def capture_aggregate(pipeline):
        captured_pipelines.append(pipeline)

        class EmptyCursor:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise StopAsyncIteration

        return EmptyCursor()

    mock_collection.aggregate = capture_aggregate

    deps = MagicMock()
    deps.settings = MagicMock()
    deps.settings.default_match_count = 10
    deps.settings.max_match_count = 50
    deps.settings.mongodb_text_index = "text_index"
    deps.settings.mongodb_collection_documents = "documents"
    deps.settings.mongodb_collection_chunks = "chunks"
    deps.db = MagicMock()
    deps.db.__getitem__ = MagicMock(return_value=mock_collection)

    await text_search(deps, "test query", tenant_id=MOCK_TENANT_ID)

    pipeline = captured_pipelines[0]
    search_stage = pipeline[0]["$search"]
    filter_clause = search_stage["compound"]["filter"]
    tenant_values = [
        f["equals"]["value"]
        for f in filter_clause
        if "equals" in f and f["equals"].get("path") == "tenant_id"
    ]
    assert tenant_values == [MOCK_TENANT_ID]


# ── Signup Email Uniqueness ─────────────────────────────────────────


@pytest.mark.unit
async def test_signup_rejects_duplicate_email():
    """Second signup with same email returns error."""
    from pymongo.errors import DuplicateKeyError

    from src.services.auth import AuthService

    users_col = MagicMock()
    tenants_col = MagicMock()
    reset_tokens_col = MagicMock()

    tenants_col.insert_one = AsyncMock()
    tenants_col.delete_one = AsyncMock()
    users_col.insert_one = AsyncMock(side_effect=DuplicateKeyError("duplicate email"))

    service = AuthService(users_col, tenants_col, reset_tokens_col)

    with pytest.raises(ValueError, match="Email is already registered"):
        await service.signup("alice@example.com", "password123", "Org A")

    # Orphaned tenant should be cleaned up
    tenants_col.delete_one.assert_called_once()


# ── Reset Token Tenant Scoping ──────────────────────────────────────


@pytest.mark.unit
async def test_reset_token_stores_tenant_id():
    """Password reset token includes tenant_id from user document."""
    from src.services.auth import AuthService

    users_col = MagicMock()
    tenants_col = MagicMock()
    reset_tokens_col = MagicMock()

    users_col.find_one = AsyncMock(return_value={
        "_id": ObjectId(),
        "email": "alice@example.com",
        "tenant_id": MOCK_TENANT_ID,
    })
    reset_tokens_col.update_many = AsyncMock()
    reset_tokens_col.insert_one = AsyncMock()

    service = AuthService(users_col, tenants_col, reset_tokens_col)
    await service.create_password_reset_token("alice@example.com")

    inserted_doc = reset_tokens_col.insert_one.call_args[0][0]
    assert inserted_doc["tenant_id"] == MOCK_TENANT_ID


# ── WebSocket Isolation ─────────────────────────────────────────────


@pytest.mark.unit
def test_websocket_rejects_without_token(client):
    """WebSocket without token is rejected."""
    with pytest.raises(Exception):
        with client.websocket_connect("/api/v1/chat/ws"):
            pass


@pytest.mark.unit
def test_websocket_rejects_forged_tenant_id(client):
    """WebSocket cannot use raw tenant_id param (old vulnerable API)."""
    # Old API used ?tenant_id=... — this should no longer work
    with pytest.raises(Exception):
        with client.websocket_connect(
            f"/api/v1/chat/ws?tenant_id={MOCK_TENANT_B_ID}"
        ):
            pass
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `cd apps/api && uv run pytest tests/test_tenant_isolation.py -v`
Expected: ALL PASS

- [ ] **Step 4: Run full test suite**

Run: `cd apps/api && uv run pytest -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```
test: add cross-tenant isolation negative tests

Verifies Tenant A cannot access Tenant B's data across chat,
documents, API keys, search, WebSocket, signup, and reset tokens.

Part of #9.
```

---

### Task 6: Final Verification and Lint

**Files:**
- All modified files

- [ ] **Step 1: Run linter**

Run: `cd apps/api && uv run ruff check .`
Expected: No errors

- [ ] **Step 2: Run formatter check**

Run: `cd apps/api && uv run ruff format --check .`
Expected: No formatting issues (or fix them)

- [ ] **Step 3: Run full test suite**

Run: `cd apps/api && uv run pytest -v`
Expected: ALL PASS

- [ ] **Step 4: Fix any issues found, then commit fixes**

If any issues: fix and commit with:
```
fix: resolve lint and formatting issues in tenant isolation
```

- [ ] **Step 5: Final commit if no issues**

No action needed — all tasks already committed individually.

---

## Summary of Changes

| Task | What | Key Files |
|------|------|-----------|
| 1 | Database indexes (unique email, tenant compounds, TTL) | `src/core/database.py`, `src/main.py` |
| 2 | Password reset token tenant scoping | `src/models/user.py`, `src/services/auth.py` |
| 3 | WebSocket JWT/API key authentication | `src/routers/chat.py`, `src/core/tenant.py` |
| 4 | Tenant guard middleware | `src/core/middleware.py`, `src/core/tenant.py`, `src/main.py` |
| 5 | Cross-tenant negative tests | `tests/test_tenant_isolation.py`, `tests/conftest.py` |
| 6 | Lint and final verification | All files |
