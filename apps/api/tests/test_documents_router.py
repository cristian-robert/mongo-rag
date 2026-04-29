"""Tests for the document CRUD router (#18).

Covers list/get/patch/delete/reingest plus tenant isolation, validation,
and cascade-delete semantics.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from tests.conftest import MOCK_TENANT_ID, make_auth_header, make_auth_header_b


def _make_doc(
    doc_id: str = "doc-1",
    tenant_id: str = MOCK_TENANT_ID,
    status: str = "ready",
    title: str = "Sample Doc",
    chunk_count: int = 5,
    source: str = "sample.pdf",
) -> dict:
    now = datetime(2026, 4, 1, tzinfo=timezone.utc)
    return {
        "_id": doc_id,
        "tenant_id": tenant_id,
        "title": title,
        "source": source,
        "status": status,
        "chunk_count": chunk_count,
        "version": 1,
        "metadata": {"foo": "bar"},
        "size_bytes": 1024,
        "format": "",
        "created_at": now,
        "updated_at": now,
        "error_message": None,
    }


@pytest.fixture
def app_client():
    """Test client with mocked deps wired through app.state."""
    from src.main import app
    from src.services.rate_limit import reset_default_limiter

    reset_default_limiter()

    deps = MagicMock()
    deps.initialize = AsyncMock()
    deps.cleanup = AsyncMock()
    deps.db = MagicMock()
    deps.settings = MagicMock()
    deps.documents_collection = MagicMock()
    deps.chunks_collection = MagicMock()
    deps.api_keys_collection = MagicMock()
    # Quota deps
    deps.subscriptions_collection = MagicMock()
    deps.subscriptions_collection.find_one = AsyncMock(
        return_value={"plan": "free", "status": "active"}
    )
    deps.usage_collection = MagicMock()
    deps.usage_collection.find_one_and_update = AsyncMock(
        return_value={
            "tenant_id": MOCK_TENANT_ID,
            "period_key": "2026-04",
            "queries_count": 1,
        }
    )

    with TestClient(app) as c:
        app.state.deps = deps
        yield c, deps


# --- list_documents ---


@pytest.mark.unit
def test_list_documents_requires_auth(app_client):
    client, _ = app_client
    response = client.get("/api/v1/documents")
    assert response.status_code == 401


@pytest.mark.unit
def test_list_documents_returns_paginated(app_client):
    client, _ = app_client
    docs = [_make_doc(f"doc-{i}", title=f"Doc {i}") for i in range(3)]

    with patch("src.routers.documents.IngestionService") as svc_cls:
        svc = MagicMock()
        svc.list_documents = AsyncMock(return_value=(docs, 3))
        svc_cls.return_value = svc

        response = client.get(
            "/api/v1/documents?page=1&page_size=10",
            headers=make_auth_header(),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 3
        assert body["page"] == 1
        assert body["page_size"] == 10
        assert len(body["items"]) == 3
        assert body["items"][0]["document_id"] == "doc-0"

        # tenant_id was forwarded from auth, not body/query
        kwargs = svc.list_documents.call_args.kwargs
        assert kwargs["tenant_id"] == MOCK_TENANT_ID


@pytest.mark.unit
def test_list_documents_passes_filters(app_client):
    client, _ = app_client

    with patch("src.routers.documents.IngestionService") as svc_cls:
        svc = MagicMock()
        svc.list_documents = AsyncMock(return_value=([], 0))
        svc_cls.return_value = svc

        response = client.get(
            "/api/v1/documents?status=ready&search=invoice&sort=title&order=asc",
            headers=make_auth_header(),
        )
        assert response.status_code == 200
        kwargs = svc.list_documents.call_args.kwargs
        assert kwargs["status"] == "ready"
        assert kwargs["search"] == "invoice"
        assert kwargs["sort"] == "title"
        assert kwargs["order"] == "asc"


@pytest.mark.unit
def test_list_documents_invalid_status_rejected(app_client):
    client, _ = app_client
    response = client.get(
        "/api/v1/documents?status=bogus",
        headers=make_auth_header(),
    )
    assert response.status_code == 422


@pytest.mark.unit
def test_list_documents_page_size_capped(app_client):
    client, _ = app_client
    response = client.get(
        "/api/v1/documents?page_size=1000",
        headers=make_auth_header(),
    )
    assert response.status_code == 422


# --- get_document ---


@pytest.mark.unit
def test_get_document_returns_record(app_client):
    client, _ = app_client
    doc = _make_doc("doc-abc", title="Abc")

    with patch("src.routers.documents.IngestionService") as svc_cls:
        svc = MagicMock()
        svc.get_document = AsyncMock(return_value=doc)
        svc_cls.return_value = svc

        response = client.get(
            "/api/v1/documents/doc-abc",
            headers=make_auth_header(),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["document_id"] == "doc-abc"
        assert body["chunk_count"] == 5
        assert body["format"] == "pdf"
        # tenant came from auth
        assert svc.get_document.call_args.args[1] == MOCK_TENANT_ID


@pytest.mark.unit
def test_get_document_not_found_for_other_tenant(app_client):
    """Cross-tenant read returns 404 (not 403) — no enumeration leak."""
    client, _ = app_client

    with patch("src.routers.documents.IngestionService") as svc_cls:
        svc = MagicMock()
        svc.get_document = AsyncMock(return_value=None)
        svc_cls.return_value = svc

        response = client.get(
            "/api/v1/documents/doc-xyz",
            headers=make_auth_header_b(),
        )
        assert response.status_code == 404


# --- update_document ---


@pytest.mark.unit
def test_patch_document_updates_title(app_client):
    client, _ = app_client
    updated = _make_doc("doc-1", title="New Title")

    with patch("src.routers.documents.IngestionService") as svc_cls:
        svc = MagicMock()
        svc.update_metadata = AsyncMock(return_value=updated)
        svc_cls.return_value = svc

        response = client.patch(
            "/api/v1/documents/doc-1",
            json={"title": "New Title"},
            headers=make_auth_header(),
        )
        assert response.status_code == 200
        assert response.json()["title"] == "New Title"


@pytest.mark.unit
def test_patch_document_rejects_empty_body(app_client):
    client, _ = app_client
    response = client.patch(
        "/api/v1/documents/doc-1",
        json={},
        headers=make_auth_header(),
    )
    assert response.status_code == 422


@pytest.mark.unit
def test_patch_document_rejects_tenant_id_in_body(app_client):
    """Forged tenant_id in the request body is rejected with 400.

    Per #44, tenant_id must NEVER come from the client. We previously
    silently dropped it via Pydantic ``extra="forbid"``; now the
    RejectClientTenantIdMiddleware fails the request closed so the bug
    surfaces immediately on either the client or an attacker.
    """
    client, _ = app_client

    with patch("src.routers.documents.IngestionService") as svc_cls:
        svc = MagicMock()
        svc.update_metadata = AsyncMock()
        svc_cls.return_value = svc

        response = client.patch(
            "/api/v1/documents/doc-1",
            json={"title": "X", "tenant_id": "evil-tenant"},
            headers=make_auth_header(),
        )
        assert response.status_code == 400
        # Service must NOT have been called — middleware bounced the request.
        svc.update_metadata.assert_not_called()


@pytest.mark.unit
def test_patch_document_not_found(app_client):
    client, _ = app_client
    with patch("src.routers.documents.IngestionService") as svc_cls:
        svc = MagicMock()
        svc.update_metadata = AsyncMock(return_value=None)
        svc_cls.return_value = svc

        response = client.patch(
            "/api/v1/documents/missing",
            json={"title": "X"},
            headers=make_auth_header(),
        )
        assert response.status_code == 404


# --- delete_document ---


@pytest.mark.unit
def test_delete_document_returns_204(app_client):
    client, _ = app_client

    with patch("src.routers.documents.IngestionService") as svc_cls:
        svc = MagicMock()
        svc.delete_document_with_cascade = AsyncMock(return_value=True)
        svc_cls.return_value = svc

        response = client.delete(
            "/api/v1/documents/doc-1",
            headers=make_auth_header(),
        )
        assert response.status_code == 204
        # Verify cascade was scoped to authed tenant
        assert svc.delete_document_with_cascade.call_args.args == ("doc-1", MOCK_TENANT_ID)


@pytest.mark.unit
def test_delete_document_not_found(app_client):
    client, _ = app_client

    with patch("src.routers.documents.IngestionService") as svc_cls:
        svc = MagicMock()
        svc.delete_document_with_cascade = AsyncMock(return_value=False)
        svc_cls.return_value = svc

        response = client.delete(
            "/api/v1/documents/missing",
            headers=make_auth_header(),
        )
        assert response.status_code == 404


# --- bulk delete ---


@pytest.mark.unit
def test_bulk_delete_documents(app_client):
    client, _ = app_client

    with patch("src.routers.documents.IngestionService") as svc_cls:
        svc = MagicMock()
        svc.bulk_delete_with_cascade = AsyncMock(return_value=2)
        svc_cls.return_value = svc

        response = client.request(
            "DELETE",
            "/api/v1/documents",
            json={"ids": ["a", "b", "c"]},
            headers=make_auth_header(),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["deleted"] == 2
        assert body["requested"] == 3
        # tenant scoped
        kwargs_or_args = svc.bulk_delete_with_cascade.call_args
        assert MOCK_TENANT_ID in kwargs_or_args.args


@pytest.mark.unit
def test_bulk_delete_requires_nonempty(app_client):
    client, _ = app_client
    response = client.request(
        "DELETE",
        "/api/v1/documents",
        json={"ids": []},
        headers=make_auth_header(),
    )
    assert response.status_code == 422


@pytest.mark.unit
def test_bulk_delete_caps_batch(app_client):
    client, _ = app_client
    response = client.request(
        "DELETE",
        "/api/v1/documents",
        json={"ids": [str(i) for i in range(101)]},
        headers=make_auth_header(),
    )
    assert response.status_code == 422


# --- reingest ---


@pytest.mark.unit
def test_reingest_marks_pending(app_client):
    client, _ = app_client
    updated = _make_doc("doc-1", status="pending")

    with patch("src.routers.documents.IngestionService") as svc_cls:
        svc = MagicMock()
        svc.mark_for_reingestion = AsyncMock(return_value=updated)
        svc_cls.return_value = svc

        response = client.post(
            "/api/v1/documents/doc-1/reingest",
            headers=make_auth_header(),
        )
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "pending"


@pytest.mark.unit
def test_reingest_409_when_processing(app_client):
    """Doc exists but is currently processing → 409."""
    client, _ = app_client
    existing = _make_doc("doc-1", status="processing")

    with patch("src.routers.documents.IngestionService") as svc_cls:
        svc = MagicMock()
        svc.mark_for_reingestion = AsyncMock(return_value=None)
        svc.get_document = AsyncMock(return_value=existing)
        svc_cls.return_value = svc

        response = client.post(
            "/api/v1/documents/doc-1/reingest",
            headers=make_auth_header(),
        )
        assert response.status_code == 409


@pytest.mark.unit
def test_reingest_404_when_missing(app_client):
    client, _ = app_client

    with patch("src.routers.documents.IngestionService") as svc_cls:
        svc = MagicMock()
        svc.mark_for_reingestion = AsyncMock(return_value=None)
        svc.get_document = AsyncMock(return_value=None)
        svc_cls.return_value = svc

        response = client.post(
            "/api/v1/documents/missing/reingest",
            headers=make_auth_header(),
        )
        assert response.status_code == 404
