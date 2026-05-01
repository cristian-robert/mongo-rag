"""Settings configuration for MongoDB RAG Agent."""

from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # MongoDB Configuration
    mongodb_uri: str = Field(..., description="MongoDB Atlas connection string")

    mongodb_database: str = Field(default="mongorag", description="MongoDB database name")

    mongodb_collection_documents: str = Field(
        default="documents", description="Collection for source documents"
    )

    mongodb_collection_chunks: str = Field(
        default="chunks", description="Collection for document chunks with embeddings"
    )

    mongodb_vector_index: str = Field(
        default="vector_index",
        description="Vector search index name (must be created in Atlas UI)",
    )

    mongodb_text_index: str = Field(
        default="text_index",
        description="Full-text search index name (must be created in Atlas UI)",
    )

    # SaaS Collection Names
    mongodb_collection_tenants: str = Field(
        default="tenants", description="Collection for tenant accounts"
    )

    mongodb_collection_users: str = Field(
        default="users", description="Collection for user accounts"
    )

    mongodb_collection_conversations: str = Field(
        default="conversations", description="Collection for chat conversations"
    )

    mongodb_collection_api_keys: str = Field(
        default="api_keys", description="Collection for API keys"
    )

    mongodb_collection_subscriptions: str = Field(
        default="subscriptions", description="Collection for billing subscriptions"
    )

    mongodb_collection_reset_tokens: str = Field(
        default="password_reset_tokens",
        description="Collection for password reset tokens",
    )

    mongodb_collection_ws_tickets: str = Field(
        default="ws_tickets",
        description="Collection for short-lived WebSocket auth tickets",
    )

    mongodb_collection_usage: str = Field(
        default="usage",
        description="Collection for per-tenant per-period usage counters",
    )

    mongodb_collection_bots: str = Field(
        default="bots",
        description="Collection for tenant-scoped bot configurations",
    )

    mongodb_collection_invitations: str = Field(
        default="invitations",
        description="Collection for pending tenant team invitations",
    )

    invitation_ttl_hours: int = Field(
        default=168,  # 7 days
        description="How long an invitation remains valid",
    )

    mongodb_collection_webhooks: str = Field(
        default="webhooks",
        description="Collection for tenant-scoped webhook subscriptions",
    )

    mongodb_collection_webhook_deliveries: str = Field(
        default="webhook_deliveries",
        description="Audit log of outbound webhook delivery attempts",
    )

    # LLM Configuration (OpenAI-compatible)
    llm_provider: str = Field(
        default="openrouter",
        description="LLM provider (openai, anthropic, gemini, ollama, etc.)",
    )

    llm_api_key: str = Field(..., description="API key for the LLM provider")

    llm_model: str = Field(
        default="anthropic/claude-haiku-4.5",
        description="Model to use for search and summarization",
    )

    llm_base_url: Optional[str] = Field(
        default="https://openrouter.ai/api/v1",
        description="Base URL for the LLM API (for OpenAI-compatible providers)",
    )

    # Embedding Configuration
    embedding_provider: str = Field(default="openai", description="Embedding provider")

    embedding_api_key: str = Field(..., description="API key for embedding provider")

    embedding_model: str = Field(
        default="text-embedding-3-small", description="Embedding model to use"
    )

    embedding_base_url: Optional[str] = Field(
        default="https://api.openai.com/v1", description="Base URL for embedding API"
    )

    embedding_dimension: int = Field(
        default=1536,
        description="Embedding vector dimension (1536 for text-embedding-3-small)",
    )

    # Search Configuration
    default_match_count: int = Field(
        default=10, description="Default number of search results to return"
    )

    max_match_count: int = Field(default=50, description="Maximum number of search results allowed")

    default_text_weight: float = Field(
        default=0.3, description="Default text weight for hybrid search (0-1)"
    )

    rrf_k: int = Field(
        default=60, ge=1, le=200, description="RRF fusion constant (default 60, standard)."
    )

    # Reranking (off by default; enable per-tenant/per-bot or globally via env)
    rerank_provider: str = Field(
        default="off",
        description="Reranker backend: 'off', 'cohere', or 'local' (cross-encoder).",
    )

    rerank_api_key: Optional[str] = Field(
        default=None,
        description="API key for hosted reranker (e.g. Cohere). Required when provider=cohere.",
    )

    rerank_model: Optional[str] = Field(
        default=None,
        description=(
            "Reranker model name. Defaults: cohere=rerank-3.5, local=ms-marco-MiniLM-L-6-v2."
        ),
    )

    rerank_top_n: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of post-RRF candidates fed to the reranker.",
    )

    rerank_timeout_seconds: float = Field(
        default=1.5,
        ge=0.1,
        le=10.0,
        description="Hard timeout for a single rerank call (graceful fallback to RRF).",
    )

    # Query rewriting (off by default)
    query_rewrite_enabled: bool = Field(
        default=False,
        description="Enable lightweight query expansion / rewriting for vague queries.",
    )

    query_rewrite_use_llm: bool = Field(
        default=False,
        description="Use LLM-based rewriter (otherwise heuristic-only).",
    )

    query_rewrite_max_expansions: int = Field(
        default=2, ge=0, le=5, description="Maximum number of additional retrieval queries."
    )

    # Redis / Celery Configuration
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for Celery broker and result backend",
    )

    # Upload Configuration
    max_upload_size_mb: int = Field(default=50, description="Maximum file upload size in MB")

    upload_temp_dir: str = Field(
        default="./.tmp/uploads",
        description=(
            "Temporary directory for FilesystemBlobStore (and the uploaded-file staging area)."
        ),
    )

    # Blob storage (ingestion handoff)
    blob_store: Literal["fs", "supabase"] = Field(
        default="fs",
        description="Backend for ingestion blob handoff: 'fs' (local) or 'supabase'.",
    )

    @field_validator("blob_store", mode="before")
    @classmethod
    def _normalize_blob_store(cls, v):
        """Accept BLOB_STORE case-insensitively before Literal validation."""
        if isinstance(v, str):
            return v.lower()
        return v

    supabase_storage_bucket: Optional[str] = Field(
        default=None,
        description="Supabase Storage bucket name. Required when blob_store='supabase'.",
    )

    supabase_s3_access_key: Optional[str] = Field(
        default=None,
        description=(
            "Supabase Storage S3 access key id. Required when blob_store='supabase'. "
            "Mint under Supabase dashboard → Project Settings → Storage → S3 Connection. "
            "NOT the service-role secret."
        ),
    )

    supabase_s3_secret_key: Optional[str] = Field(
        default=None,
        description=(
            "Supabase Storage S3 secret. Required when blob_store='supabase'. "
            "Mint alongside supabase_s3_access_key in the dashboard."
        ),
    )

    supabase_s3_region: str = Field(
        default="us-east-1",
        description="boto3 region label for the Supabase S3-compatible endpoint.",
    )

    # URL Ingestion Configuration
    url_fetch_timeout_seconds: float = Field(
        default=30.0,
        description="Total timeout for fetching a remote URL (connect + read)",
    )

    url_fetch_max_redirects: int = Field(
        default=3,
        description="Maximum redirects to follow when fetching a URL",
    )

    url_fetch_max_size_mb: int = Field(
        default=25,
        description="Maximum response size in MB for URL ingestion",
    )

    url_fetch_allow_private_ips: bool = Field(
        default=False,
        description=(
            "Allow URL fetcher to connect to private/loopback/link-local IP ranges. "
            "MUST stay false in production — only flip on for tests against localhost."
        ),
    )

    # Auth Configuration
    nextauth_secret: str = Field(
        ..., description="Shared secret for JWT signing (same as NEXTAUTH_SECRET in frontend)"
    )

    # --- Supabase Auth ---
    # The backend verifies Supabase-issued JWTs. Verification path:
    # 1. If a SUPABASE_JWT_SECRET is configured AND the token is HS256 → verify with shared secret
    # 2. Otherwise (RS256/ES256/etc.) → fetch & cache JWKS from
    #    https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json and verify by `kid`
    # Issuer / audience are pinned from these settings, never from the token itself.
    supabase_url: Optional[str] = Field(
        default=None,
        description=(
            "Supabase project URL, e.g. https://<project-ref>.supabase.co. "
            "When set, Supabase JWTs are accepted and the backend pins the expected issuer "
            "to <supabase_url>/auth/v1."
        ),
    )

    supabase_project_ref: Optional[str] = Field(
        default=None,
        description=(
            "Supabase project ref (shorthand). Optional — derived from supabase_url when omitted."
        ),
    )

    supabase_jwt_secret: Optional[str] = Field(
        default=None,
        description=(
            "Supabase legacy HS256 shared JWT secret. Optional — when omitted, the backend "
            "verifies via the project's JWKS endpoint. Server-only; never expose to clients."
        ),
    )

    supabase_jwt_audience: str = Field(
        default="authenticated",
        description=(
            "Expected `aud` claim on Supabase user JWTs. Defaults to 'authenticated' "
            "(Supabase's standard for signed-in users)."
        ),
    )

    supabase_jwks_cache_seconds: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="How long to cache the Supabase JWKS document (seconds).",
    )

    @property
    def supabase_issuer(self) -> Optional[str]:
        """Expected `iss` claim for Supabase-signed user JWTs.

        Returns None when Supabase is not configured (Supabase auth disabled).
        """
        if not self.supabase_url:
            return None
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @property
    def supabase_jwks_url(self) -> Optional[str]:
        """JWKS endpoint URL for the configured Supabase project."""
        if not self.supabase_url:
            return None
        return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"

    resend_api_key: Optional[str] = Field(
        default=None,
        description="Resend API key for transactional emails (required for password reset)",
    )

    app_url: str = Field(
        default="http://localhost:3100",
        description="Frontend app URL (used in password reset email links)",
    )

    # Application environment — gates dev-only relaxations
    app_env: str = Field(
        default="development",
        description="Environment label: development, staging, production",
    )

    # CORS configuration — explicit allow-list, no wildcards in production
    cors_allowed_origins: str = Field(
        default="http://localhost:3100",
        description=(
            "Comma-separated list of allowed CORS origins for the dashboard. "
            "Production must enumerate explicit origins — no wildcards."
        ),
    )

    # Maximum allowed request body size (bytes) for non-multipart endpoints.
    # File uploads use max_upload_size_mb separately.
    max_request_body_bytes: int = Field(
        default=1_048_576,  # 1 MiB
        description="Maximum body size for JSON/form requests (bytes).",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated origins into a clean list."""
        return [o.strip() for o in (self.cors_allowed_origins or "").split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        """Whether the app is running in production mode."""
        return self.app_env.lower() == "production"

    reset_email_from: str = Field(
        default="noreply@mongorag.com",
        description="From address for password reset emails",
    )

    # API key validation backend (#42) -- Postgres connection itself is
    # configured via SUPABASE_DB_URL on the existing pool (`src.core.postgres`).
    api_key_backend: Literal["postgres", "mongo"] = Field(
        default="postgres",
        description=(
            "Which store to validate API keys against. 'postgres' is the new "
            "default (#42); 'mongo' is kept for emergency rollback."
        ),
    )

    # Stripe Configuration
    stripe_secret_key: Optional[str] = Field(
        default=None,
        description="Stripe secret API key (sk_test_... in test mode, sk_live_... in production)",
    )

    stripe_publishable_key: Optional[str] = Field(
        default=None,
        description=(
            "Stripe publishable key (pk_test_... / pk_live_...) — safe to expose to clients"
        ),
    )

    stripe_webhook_secret: Optional[str] = Field(
        default=None,
        description="Stripe webhook signing secret (whsec_...) — used by webhook handler in #43",
    )

    stripe_webhook_tolerance_seconds: int = Field(
        default=300,
        ge=30,
        le=3600,
        description=(
            "Replay-attack tolerance window in seconds for Stripe webhook timestamp "
            "verification. Stripe's default is 300 (5 minutes)."
        ),
    )

    # Supabase Postgres connection — used by webhook handler (service-role, bypasses RLS).
    supabase_db_url: Optional[str] = Field(
        default=None,
        description=(
            "Postgres connection string for Supabase (asyncpg-compatible). When unset, "
            "Postgres-backed operations (e.g. Stripe webhook persistence) raise 503."
        ),
    )

    supabase_db_pool_min: int = Field(
        default=1, ge=0, le=20, description="asyncpg pool minimum size"
    )

    supabase_db_pool_max: int = Field(
        default=5, ge=1, le=50, description="asyncpg pool maximum size"
    )

    # Observability Configuration
    log_level: str = Field(
        default="INFO",
        description="Root log level (DEBUG, INFO, WARNING, ERROR)",
    )

    sentry_dsn: Optional[str] = Field(
        default=None,
        description="Sentry DSN — when unset, Sentry is a graceful no-op",
    )

    sentry_traces_sample_rate: float = Field(
        default=0.0,
        description="Sentry performance trace sample rate (0.0 = off)",
    )

    sentry_release: Optional[str] = Field(
        default=None,
        description="Release identifier surfaced in Sentry events",
    )

    # Stripe Price IDs — one per (plan, model_tier) combination.
    stripe_price_pro_starter: Optional[str] = Field(default=None)
    stripe_price_pro_standard: Optional[str] = Field(default=None)
    stripe_price_pro_premium: Optional[str] = Field(default=None)
    stripe_price_pro_ultra: Optional[str] = Field(default=None)
    stripe_price_enterprise_starter: Optional[str] = Field(default=None)
    stripe_price_enterprise_standard: Optional[str] = Field(default=None)
    stripe_price_enterprise_premium: Optional[str] = Field(default=None)
    stripe_price_enterprise_ultra: Optional[str] = Field(default=None)


def load_settings() -> Settings:
    """Load settings with proper error handling."""
    try:
        return Settings()
    except Exception as e:
        error_msg = f"Failed to load settings: {e}"
        if "mongodb_uri" in str(e).lower():
            error_msg += "\nMake sure to set MONGODB_URI in your .env file"
        if "llm_api_key" in str(e).lower():
            error_msg += "\nMake sure to set LLM_API_KEY in your .env file"
        if "embedding_api_key" in str(e).lower():
            error_msg += "\nMake sure to set EMBEDDING_API_KEY in your .env file"
        raise ValueError(error_msg) from e
