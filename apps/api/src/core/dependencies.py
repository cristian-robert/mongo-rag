"""Dependencies for MongoDB RAG Agent."""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import openai
from pymongo import AsyncMongoClient
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from src.core.settings import Settings, load_settings

logger = logging.getLogger(__name__)


@dataclass
class AgentDependencies:
    """Dependencies injected into the agent context."""

    # Core dependencies
    mongo_client: Optional[AsyncMongoClient] = None
    db: Optional[AsyncDatabase] = None
    openai_client: Optional[openai.AsyncOpenAI] = None
    settings: Optional[Settings] = None

    # Session context
    session_id: Optional[str] = None
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    query_history: list = field(default_factory=list)

    async def initialize(self) -> None:
        """
        Initialize external connections.

        Raises:
            ConnectionFailure: If MongoDB connection fails
            ServerSelectionTimeoutError: If MongoDB server selection times out
            ValueError: If settings cannot be loaded
        """
        if self.settings is None:
            self.settings = load_settings()
            logger.info("settings_loaded", extra={"database": self.settings.mongodb_database})

        # Initialize MongoDB client with connection pooling
        if self.mongo_client is None:
            try:
                self.mongo_client = AsyncMongoClient(
                    self.settings.mongodb_uri,
                    serverSelectionTimeoutMS=5000,
                    maxPoolSize=10,
                    minPoolSize=1,
                    maxIdleTimeMS=30000,
                    retryWrites=True,
                    retryReads=True,
                )
                self.db = self.mongo_client[self.settings.mongodb_database]

                # Verify connection with ping
                await self.mongo_client.admin.command("ping")
                logger.info(
                    "mongodb_connected",
                    extra={"database": self.settings.mongodb_database},
                )
            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                logger.exception("mongodb_connection_failed", extra={"error": str(e)})
                raise

        # Initialize OpenAI client for embeddings
        if self.openai_client is None:
            self.openai_client = openai.AsyncOpenAI(
                api_key=self.settings.embedding_api_key,
                base_url=self.settings.embedding_base_url,
            )
            logger.info(
                "openai_client_initialized",
                extra={
                    "model": self.settings.embedding_model,
                    "dimension": self.settings.embedding_dimension,
                },
            )

    # -- Collection accessors --

    def _get_collection(self, name: str) -> AsyncCollection:
        """Get a MongoDB collection by name. Requires initialize() first."""
        if self.db is None:
            raise RuntimeError("Dependencies not initialized. Call initialize() first.")
        return self.db[name]

    @property
    def chunks_collection(self) -> AsyncCollection:
        return self._get_collection(self.settings.mongodb_collection_chunks)

    @property
    def documents_collection(self) -> AsyncCollection:
        return self._get_collection(self.settings.mongodb_collection_documents)

    @property
    def tenants_collection(self) -> AsyncCollection:
        return self._get_collection(self.settings.mongodb_collection_tenants)

    @property
    def users_collection(self) -> AsyncCollection:
        return self._get_collection(self.settings.mongodb_collection_users)

    @property
    def conversations_collection(self) -> AsyncCollection:
        return self._get_collection(self.settings.mongodb_collection_conversations)

    @property
    def api_keys_collection(self) -> AsyncCollection:
        return self._get_collection(self.settings.mongodb_collection_api_keys)

    @property
    def subscriptions_collection(self) -> AsyncCollection:
        return self._get_collection(self.settings.mongodb_collection_subscriptions)

    @property
    def reset_tokens_collection(self) -> AsyncCollection:
        return self._get_collection(self.settings.mongodb_collection_reset_tokens)

    @property
    def ws_tickets_collection(self) -> AsyncCollection:
        return self._get_collection(self.settings.mongodb_collection_ws_tickets)

    @property
    def usage_collection(self) -> AsyncCollection:
        return self._get_collection(self.settings.mongodb_collection_usage)

    @property
    def bots_collection(self) -> AsyncCollection:
        return self._get_collection(self.settings.mongodb_collection_bots)

    @property
    def invitations_collection(self) -> AsyncCollection:
        return self._get_collection(self.settings.mongodb_collection_invitations)

    @property
    def webhooks_collection(self) -> AsyncCollection:
        return self._get_collection(self.settings.mongodb_collection_webhooks)

    @property
    def webhook_deliveries_collection(self) -> AsyncCollection:
        return self._get_collection(self.settings.mongodb_collection_webhook_deliveries)

    # -- Core methods --

    async def cleanup(self) -> None:
        """Clean up external connections."""
        if self.mongo_client is not None:
            await self.mongo_client.close()
            self.mongo_client = None
            self.db = None
            logger.info("mongodb_connection_closed")

    async def get_embedding(self, text: str) -> list[float]:
        """
        Generate embedding for text using OpenAI.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats

        Raises:
            Exception: If embedding generation fails
        """
        if self.openai_client is None:
            await self.initialize()

        response = await self.openai_client.embeddings.create(
            model=self.settings.embedding_model, input=text
        )
        # Return as list of floats - MongoDB stores as native array
        return response.data[0].embedding

    def set_user_preference(self, key: str, value: Any) -> None:
        """
        Set a user preference for the session.

        Args:
            key: Preference key
            value: Preference value
        """
        self.user_preferences[key] = value

    def add_to_history(self, query: str) -> None:
        """
        Add a query to the search history.

        Args:
            query: Search query to add to history
        """
        self.query_history.append(query)
        # Keep only last 10 queries
        if len(self.query_history) > 10:
            self.query_history.pop(0)
