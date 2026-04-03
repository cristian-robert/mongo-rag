"""Tests for auth-related settings."""


import pytest


@pytest.mark.unit
def test_settings_loads_auth_fields(monkeypatch):
    """Settings includes NEXTAUTH_SECRET and other auth fields."""
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")
    monkeypatch.setenv("NEXTAUTH_SECRET", "test-secret-at-least-32-chars-long!!")
    monkeypatch.setenv("RESEND_API_KEY", "re_test_123")

    from src.core.settings import Settings

    settings = Settings()
    assert settings.nextauth_secret == "test-secret-at-least-32-chars-long!!"
    assert settings.resend_api_key == "re_test_123"
    assert settings.app_url == "http://localhost:3100"
    assert settings.reset_email_from == "noreply@mongorag.com"


@pytest.mark.unit
def test_settings_requires_nextauth_secret(monkeypatch):
    """Settings raises if NEXTAUTH_SECRET is missing."""
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")
    monkeypatch.delenv("NEXTAUTH_SECRET", raising=False)

    from src.core.settings import Settings

    with pytest.raises(Exception):
        Settings()
