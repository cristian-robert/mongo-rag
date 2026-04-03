"""Tests for ingestion router."""

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from tests.conftest import make_auth_header


@pytest.fixture
def app_client():
    """Create test client with mocked Celery and MongoDB."""
    from src.main import app

    mock_deps = MagicMock()
    mock_deps.initialize = AsyncMock()
    mock_deps.cleanup = AsyncMock()
    mock_deps.db = MagicMock()
    mock_deps.settings = MagicMock()
    mock_deps.settings.max_upload_size_mb = 50
    mock_deps.settings.upload_temp_dir = "/tmp/test-uploads"
    mock_deps.documents_collection = MagicMock()
    mock_deps.documents_collection.insert_one = AsyncMock(
        return_value=MagicMock(inserted_id="doc-test-123")
    )
    mock_deps.documents_collection.find_one = AsyncMock(return_value=None)
    mock_deps.chunks_collection = MagicMock()

    with TestClient(app) as c:
        app.state.deps = mock_deps  # Override after lifespan runs
        yield c, mock_deps


@pytest.mark.unit
def test_ingest_missing_auth_header(app_client):
    """Ingest without Authorization header returns 401."""
    client, _ = app_client
    file = io.BytesIO(b"test content")
    response = client.post(
        "/api/v1/documents/ingest",
        files={"file": ("test.txt", file, "text/plain")},
    )
    assert response.status_code == 401


@pytest.mark.unit
def test_ingest_unsupported_format(app_client):
    """Ingest with unsupported file format returns 422."""
    client, _ = app_client
    file = io.BytesIO(b"test content")
    response = client.post(
        "/api/v1/documents/ingest",
        files={"file": ("test.exe", file, "application/octet-stream")},
        headers=make_auth_header(),
    )
    assert response.status_code == 422


@pytest.mark.unit
def test_ingest_valid_file_returns_202(app_client):
    """Ingest with valid file returns 202 Accepted."""
    client, mock_deps = app_client

    with (
        patch("src.routers.ingest.ingest_document") as mock_task,
        patch("src.routers.ingest.IngestionService") as mock_service_cls,
        patch("os.makedirs"),
        patch("builtins.open", create=True),
        patch("shutil.copyfileobj"),
        patch("os.path.getsize", return_value=1024),
    ):
        mock_task.delay.return_value = MagicMock(id="celery-task-123")

        mock_service = MagicMock()
        mock_service.create_pending_document = AsyncMock(return_value="doc-test-123")
        mock_service_cls.return_value = mock_service

        file = io.BytesIO(b"# Test Document\n\nSome content here.")
        response = client.post(
            "/api/v1/documents/ingest",
            files={"file": ("test.md", file, "text/markdown")},
            headers=make_auth_header(),
        )

        assert response.status_code == 202
        data = response.json()
        assert data["document_id"] == "doc-test-123"
        assert data["status"] == "pending"
        assert "task_id" in data


@pytest.mark.unit
def test_document_status_returns_status(app_client):
    """GET document status returns current document status."""
    client, mock_deps = app_client

    with patch("src.routers.ingest.IngestionService") as mock_service_cls:
        mock_service = MagicMock()
        mock_service.get_document_status = AsyncMock(
            return_value={
                "_id": "doc-123",
                "status": "ready",
                "chunk_count": 42,
                "version": 1,
                "title": "Test Doc",
            }
        )
        mock_service_cls.return_value = mock_service

        response = client.get(
            "/api/v1/documents/doc-123/status",
            headers=make_auth_header(),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["chunk_count"] == 42


@pytest.mark.unit
def test_document_status_not_found(app_client):
    """GET document status for nonexistent document returns 404."""
    client, mock_deps = app_client

    with patch("src.routers.ingest.IngestionService") as mock_service_cls:
        mock_service = MagicMock()
        mock_service.get_document_status = AsyncMock(return_value=None)
        mock_service_cls.return_value = mock_service

        response = client.get(
            "/api/v1/documents/nonexistent/status",
            headers=make_auth_header(),
        )

        assert response.status_code == 404
