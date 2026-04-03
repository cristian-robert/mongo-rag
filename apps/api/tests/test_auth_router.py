"""Tests for auth router endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def auth_client(mock_deps):
    """Create test client with auth-ready mocked deps."""
    from src.main import app

    # Add auth-related collection mocks
    mock_deps.users_collection = MagicMock()
    mock_deps.tenants_collection = MagicMock()
    mock_deps.reset_tokens_collection = MagicMock()

    with TestClient(app) as c:
        app.state.deps = mock_deps
        yield c


@pytest.mark.unit
def test_signup_success(auth_client, mock_deps):
    """POST /auth/signup creates tenant and user."""
    with patch("src.routers.auth.AuthService") as mock_service:
        instance = mock_service.return_value
        instance.signup = AsyncMock(
            return_value={
                "user_id": "user-123",
                "tenant_id": "tenant-abc",
                "email": "test@example.com",
            }
        )

        response = auth_client.post(
            "/api/v1/auth/signup",
            json={
                "email": "test@example.com",
                "password": "securepass123",
                "organization_name": "Test Corp",
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == "user-123"
    assert data["tenant_id"] == "tenant-abc"
    assert data["email"] == "test@example.com"


@pytest.mark.unit
def test_signup_duplicate_email(auth_client, mock_deps):
    """POST /auth/signup returns 409 for duplicate email."""
    with patch("src.routers.auth.AuthService") as mock_service:
        instance = mock_service.return_value
        instance.signup = AsyncMock(side_effect=ValueError("Email is already registered"))

        response = auth_client.post(
            "/api/v1/auth/signup",
            json={
                "email": "test@example.com",
                "password": "securepass123",
                "organization_name": "Test Corp",
            },
        )

    assert response.status_code == 409
    assert "already registered" in response.json()["detail"]


@pytest.mark.unit
def test_signup_invalid_email(auth_client):
    """POST /auth/signup returns 422 for invalid email."""
    response = auth_client.post(
        "/api/v1/auth/signup",
        json={
            "email": "not-an-email",
            "password": "securepass123",
            "organization_name": "Test Corp",
        },
    )
    assert response.status_code == 422


@pytest.mark.unit
def test_signup_short_password(auth_client):
    """POST /auth/signup returns 422 for password under 8 chars."""
    response = auth_client.post(
        "/api/v1/auth/signup",
        json={
            "email": "test@example.com",
            "password": "short",
            "organization_name": "Test Corp",
        },
    )
    assert response.status_code == 422


@pytest.mark.unit
def test_login_success(auth_client, mock_deps):
    """POST /auth/login returns user data for valid credentials."""
    with patch("src.routers.auth.AuthService") as mock_service:
        instance = mock_service.return_value
        instance.login = AsyncMock(
            return_value={
                "user_id": "user-123",
                "tenant_id": "tenant-abc",
                "email": "test@example.com",
                "name": "Test User",
                "role": "owner",
            }
        )

        response = auth_client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "securepass123"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "user-123"
    assert data["tenant_id"] == "tenant-abc"
    assert data["role"] == "owner"


@pytest.mark.unit
def test_login_invalid_credentials(auth_client, mock_deps):
    """POST /auth/login returns 401 for wrong password."""
    with patch("src.routers.auth.AuthService") as mock_service:
        instance = mock_service.return_value
        instance.login = AsyncMock(side_effect=ValueError("Invalid email or password"))

        response = auth_client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "wrongpass"},
        )

    assert response.status_code == 401
    assert "Invalid" in response.json()["detail"]


@pytest.mark.unit
def test_forgot_password_success(auth_client, mock_deps):
    """POST /auth/forgot-password returns 200 regardless of email existence."""
    with patch("src.routers.auth.AuthService") as mock_service:
        instance = mock_service.return_value
        instance.create_password_reset_token = AsyncMock(return_value="raw-token-123")

        with patch("src.routers.auth._send_reset_email") as mock_send:
            mock_send.return_value = None

            response = auth_client.post(
                "/api/v1/auth/forgot-password",
                json={"email": "test@example.com"},
            )

    assert response.status_code == 200
    assert "check your email" in response.json()["message"].lower()


@pytest.mark.unit
def test_forgot_password_unknown_email(auth_client, mock_deps):
    """POST /auth/forgot-password returns 200 even for unknown email."""
    with patch("src.routers.auth.AuthService") as mock_service:
        instance = mock_service.return_value
        instance.create_password_reset_token = AsyncMock(return_value=None)

        response = auth_client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "nobody@example.com"},
        )

    # Same 200 response — no email enumeration
    assert response.status_code == 200


@pytest.mark.unit
def test_reset_password_success(auth_client, mock_deps):
    """POST /auth/reset-password returns 200 for valid token."""
    with patch("src.routers.auth.AuthService") as mock_service:
        instance = mock_service.return_value
        instance.reset_password = AsyncMock(return_value=None)

        response = auth_client.post(
            "/api/v1/auth/reset-password",
            json={"token": "valid-token-abc", "new_password": "newpassword123"},
        )

    assert response.status_code == 200


@pytest.mark.unit
def test_reset_password_invalid_token(auth_client, mock_deps):
    """POST /auth/reset-password returns 400 for invalid token."""
    with patch("src.routers.auth.AuthService") as mock_service:
        instance = mock_service.return_value
        instance.reset_password = AsyncMock(
            side_effect=ValueError("Invalid or expired reset token")
        )

        response = auth_client.post(
            "/api/v1/auth/reset-password",
            json={"token": "bogus-token", "new_password": "newpassword123"},
        )

    assert response.status_code == 400
