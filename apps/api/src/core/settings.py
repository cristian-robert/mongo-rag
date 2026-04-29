"""Settings configuration for MongoDB RAG Agent."""

from typing import Optional

from dotenv import load_dotenv
from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = ConfigDict(
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

    # Redis / Celery Configuration
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for Celery broker and result backend",
    )

    # Upload Configuration
    max_upload_size_mb: int = Field(default=50, description="Maximum file upload size in MB")

    upload_temp_dir: str = Field(
        default="/tmp/mongorag-uploads", description="Temporary directory for uploaded files"
    )

    # Auth Configuration
    nextauth_secret: str = Field(
        ..., description="Shared secret for JWT signing (same as NEXTAUTH_SECRET in frontend)"
    )

    resend_api_key: Optional[str] = Field(
        default=None,
        description="Resend API key for transactional emails (required for password reset)",
    )

    app_url: str = Field(
        default="http://localhost:3100",
        description="Frontend app URL (used in password reset email links)",
    )

    reset_email_from: str = Field(
        default="noreply@mongorag.com",
        description="From address for password reset emails",
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
