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
def test_settings_resend_api_key_optional(monkeypatch):
    """Settings loads without RESEND_API_KEY (it's optional)."""
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")
    monkeypatch.setenv("NEXTAUTH_SECRET", "test-secret-at-least-32-chars-long!!")
    monkeypatch.delenv("RESEND_API_KEY", raising=False)

    from src.core.settings import Settings

    settings = Settings()
    assert settings.resend_api_key is None


def test_blob_store_defaults_to_fs(monkeypatch):
    monkeypatch.delenv("BLOB_STORE", raising=False)
    from src.core.settings import Settings
    s = Settings()
    assert s.blob_store == "fs"
    assert s.supabase_storage_bucket is None
    assert s.supabase_s3_region == "us-east-1"


def test_blob_store_supabase_requires_bucket(monkeypatch):
    monkeypatch.setenv("BLOB_STORE", "supabase")
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "mongorag-uploads")
    from src.core.settings import Settings
    s = Settings()
    assert s.blob_store == "supabase"
    assert s.supabase_storage_bucket == "mongorag-uploads"
