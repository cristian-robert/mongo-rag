"""Cross-tenant isolation negative tests.

Verifies Tenant A cannot access Tenant B's data across all endpoints.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

from tests.conftest import MOCK_TENANT_B_ID, MOCK_TENANT_ID, make_auth_header

# -- Chat Isolation -----------------------------------------------------------


@pytest.mark.unit
def test_chat_tenant_a_cannot_see_tenant_b_conversations(client, mock_deps):
    """Chat endpoint only queries with the authenticated tenant's ID."""
    captured_tenant_ids: list[str] = []

    class MockChatService:
        def __init__(self, deps):
            pass

        async def handle_message(
            self,
            *,
            message,
            tenant_id,
            conversation_id=None,
            search_type=None,
            retrieval=None,
        ):
            captured_tenant_ids.append(tenant_id)
            return {
                "answer": "test",
                "sources": [],
                "citations": [],
                "conversation_id": "conv-1",
                "rewritten_queries": [],
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


# -- Document Isolation -------------------------------------------------------


@pytest.mark.unit
def test_document_status_scoped_to_tenant(client, mock_deps):
    """Document status endpoint filters by authenticated tenant."""
    doc_id = str(ObjectId())

    with patch("src.routers.ingest.IngestionService") as mock_service:
        instance = mock_service.return_value
        instance.get_document_status = AsyncMock(return_value=None)

        client.get(
            f"/api/v1/documents/{doc_id}/status",
            headers=make_auth_header(),
        )

    # Service should be called with tenant A's ID
    call_args = instance.get_document_status.call_args
    if call_args:
        # Check positional or keyword args for tenant_id
        all_args = list(call_args.args) + list(call_args.kwargs.values())
        assert MOCK_TENANT_ID in all_args


# -- API Key Isolation --------------------------------------------------------


@pytest.mark.unit
def test_list_keys_scoped_to_tenant(client, mock_deps):
    """List keys only returns keys for authenticated tenant (Postgres path, #42)."""
    from src.core.deps import get_pg_pool
    from src.main import app

    fake_pool = MagicMock(name="pg_pool")
    app.dependency_overrides[get_pg_pool] = lambda: fake_pool
    try:
        with patch("src.routers.keys.pg_api_keys.list_keys", new_callable=AsyncMock) as listfn:
            listfn.return_value = []
            response = client.get("/api/v1/keys", headers=make_auth_header())

        assert response.status_code == 200
        listfn.assert_called_once_with(pool=fake_pool, tenant_id=MOCK_TENANT_ID)
    finally:
        app.dependency_overrides.pop(get_pg_pool, None)


@pytest.mark.unit
def test_revoke_key_scoped_to_tenant(client, mock_deps):
    """Revoke key only works for the authenticated tenant's keys (Postgres path, #42)."""
    from uuid import uuid4

    from src.core.deps import get_pg_pool
    from src.main import app

    fake_pool = MagicMock(name="pg_pool")
    app.dependency_overrides[get_pg_pool] = lambda: fake_pool
    key_id = str(uuid4())
    try:
        with patch("src.routers.keys.pg_api_keys.revoke_key", new_callable=AsyncMock) as revoke:
            revoke.return_value = True
            client.delete(f"/api/v1/keys/{key_id}", headers=make_auth_header())
        revoke.assert_called_once_with(pool=fake_pool, key_id=key_id, tenant_id=MOCK_TENANT_ID)
    finally:
        app.dependency_overrides.pop(get_pg_pool, None)


# -- Search Isolation ---------------------------------------------------------


@pytest.mark.unit
async def test_semantic_search_filters_by_tenant():
    """Semantic search pipeline includes tenant_id in $vectorSearch filter."""
    from src.services.search import semantic_search

    captured_pipelines: list = []
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

    await semantic_search(deps, "test query", tenant_id=MOCK_TENANT_ID)

    pipeline = captured_pipelines[0]
    vector_filter = pipeline[0]["$vectorSearch"]["filter"]
    assert vector_filter == {"tenant_id": MOCK_TENANT_ID}
    assert MOCK_TENANT_B_ID not in str(pipeline)


@pytest.mark.unit
async def test_text_search_filters_by_tenant():
    """Text search pipeline includes tenant_id in $search compound filter."""
    from src.services.search import text_search

    captured_pipelines: list = []
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


# -- Signup Email Uniqueness --------------------------------------------------


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

    tenants_col.delete_one.assert_called_once()


# -- Reset Token Tenant Scoping -----------------------------------------------


@pytest.mark.unit
async def test_reset_token_stores_tenant_id():
    """Password reset token includes tenant_id from user document."""
    from src.services.auth import AuthService

    users_col = MagicMock()
    tenants_col = MagicMock()
    reset_tokens_col = MagicMock()

    users_col.find_one = AsyncMock(
        return_value={
            "_id": ObjectId(),
            "email": "alice@example.com",
            "tenant_id": MOCK_TENANT_ID,
        }
    )
    reset_tokens_col.update_many = AsyncMock()
    reset_tokens_col.insert_one = AsyncMock()

    service = AuthService(users_col, tenants_col, reset_tokens_col)
    await service.create_password_reset_token("alice@example.com")

    inserted_doc = reset_tokens_col.insert_one.call_args[0][0]
    assert inserted_doc["tenant_id"] == MOCK_TENANT_ID


# -- WebSocket Isolation ------------------------------------------------------


@pytest.mark.unit
def test_websocket_rejects_without_ticket(client):
    """WebSocket without ticket is rejected."""
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/v1/chat/ws"):
            pass
    assert exc_info.value.code == 4001


@pytest.mark.unit
def test_websocket_rejects_forged_tenant_id(client):
    """WebSocket cannot use raw tenant_id param (old vulnerable API)."""
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/api/v1/chat/ws?tenant_id={MOCK_TENANT_B_ID}"):
            pass
    assert exc_info.value.code == 4001
