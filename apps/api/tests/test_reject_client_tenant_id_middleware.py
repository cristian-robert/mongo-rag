"""Middleware: reject any inbound request that supplies tenant_id itself."""

from unittest.mock import patch

import pytest

from tests.conftest import MOCK_TENANT_B_ID, MOCK_TENANT_ID, make_auth_header


@pytest.mark.unit
def test_query_param_tenant_id_is_rejected(client) -> None:
    response = client.get(
        f"/api/v1/keys?tenant_id={MOCK_TENANT_B_ID}",
        headers=make_auth_header(),
    )
    assert response.status_code == 400
    assert "tenant_id" in response.json()["detail"]


@pytest.mark.unit
def test_path_segment_tenant_id_is_rejected(client) -> None:
    response = client.get(
        "/api/v1/tenant_id/some-id",
        headers=make_auth_header(),
    )
    assert response.status_code == 400


@pytest.mark.unit
def test_json_body_with_tenant_id_is_rejected(client) -> None:
    """Even a forged tenant_id at top level of a JSON body is bounced."""
    response = client.post(
        "/api/v1/chat",
        json={"message": "hello", "tenant_id": MOCK_TENANT_B_ID},
        headers=make_auth_header(),
    )
    assert response.status_code == 400
    assert "tenant_id" in response.json()["detail"]


@pytest.mark.unit
def test_json_body_with_nested_tenant_id_is_rejected(client) -> None:
    """Nested tenant_id is also caught (defense in depth)."""
    response = client.post(
        "/api/v1/chat",
        json={"message": "hello", "retrieval": {"tenant_id": MOCK_TENANT_B_ID}},
        headers=make_auth_header(),
    )
    assert response.status_code == 400


@pytest.mark.unit
def test_clean_request_passes(client) -> None:
    """Valid request with no client tenant_id reaches the handler."""

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
            assert tenant_id == MOCK_TENANT_ID
            return {
                "answer": "ok",
                "sources": [],
                "citations": [],
                "conversation_id": "c-1",
                "rewritten_queries": [],
            }

    with patch("src.routers.chat.ChatService", MockChatService):
        response = client.post(
            "/api/v1/chat",
            json={"message": "hello"},
            headers=make_auth_header(),
        )
    assert response.status_code == 200, response.text


@pytest.mark.unit
def test_user_uploaded_text_containing_tenant_id_substring_is_allowed(client) -> None:
    """The middleware parses JSON; substring-only matches must NOT trigger 400.

    A document body whose content happens to contain the literal string
    ``tenant_id`` (e.g. a markdown file describing this very middleware)
    should ingest cleanly because the JSON has no ``tenant_id`` *key*.
    """
    # Use the chat endpoint with the literal substring inside a value field.
    payload = {"message": "tell me about tenant_id isolation"}

    captured: list[str] = []

    class MockChatService:
        def __init__(self, deps):
            pass

        async def handle_message(self, *, message, tenant_id, **_):
            captured.append(message)
            return {
                "answer": "ok",
                "sources": [],
                "citations": [],
                "conversation_id": "c-1",
                "rewritten_queries": [],
            }

    with patch("src.routers.chat.ChatService", MockChatService):
        response = client.post(
            "/api/v1/chat",
            json=payload,
            headers=make_auth_header(),
        )

    assert response.status_code == 200, response.text
    assert captured == [payload["message"]]


@pytest.mark.unit
def test_oversized_body_is_passed_through_without_scan(client) -> None:
    """A body over the 1 MiB scan cap is allowed past the middleware.

    The handler still derives tenant_id from auth, so the request is safe;
    the middleware just refuses to buffer enormous payloads in memory.
    """
    huge_message = "a" * (2 * 1024 * 1024)  # 2 MiB
    response = client.post(
        "/api/v1/chat",
        json={"message": huge_message},
        headers=make_auth_header(),
    )
    # The body-size middleware will reject this with 413 before the
    # tenant-id middleware even gets a chance — which is also correct.
    # We only assert the tenant-id middleware did not 400 it.
    assert response.status_code != 400
