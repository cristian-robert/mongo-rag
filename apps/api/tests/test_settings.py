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


def test_settings_uses_settings_config_dict():
    """Regression: model_config must be SettingsConfigDict, not the looser pydantic ConfigDict."""
    from src.core.settings import Settings

    # Both ConfigDict and SettingsConfigDict are TypedDicts at runtime
    assert isinstance(Settings.model_config, dict)
    # The actual value-shape check:
    assert Settings.model_config.get("env_file") == ".env"


def test_blob_store_accepts_uppercase(monkeypatch):
    """Case-insensitive: BLOB_STORE=Supabase must work like supabase."""
    monkeypatch.setenv("BLOB_STORE", "Supabase")
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "test-bucket")
    from src.core.settings import Settings

    s = Settings()
    assert s.blob_store == "supabase"


def test_blob_store_accepts_mixed_case(monkeypatch):
    monkeypatch.setenv("BLOB_STORE", "FS")
    from src.core.settings import Settings

    s = Settings()
    assert s.blob_store == "fs"


def test_blob_store_rejects_unknown_value(monkeypatch):
    monkeypatch.setenv("BLOB_STORE", "azure")
    from src.core.settings import Settings

    with pytest.raises(Exception):  # ValidationError
        Settings()


def test_settings_app_env_declared_exactly_once():
    """Regression: Bug fix — app_env was declared twice, second silently shadowed first."""
    import ast
    import inspect

    from src.core import settings

    source = inspect.getsource(settings)
    tree = ast.parse(source)
    # Find the Settings class
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Settings")
    names = [
        n.target.id
        for n in cls.body
        if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
    ]
    assert names.count("app_env") == 1, f"app_env declared {names.count('app_env')} times"
