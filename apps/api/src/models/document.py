"""Document and chunk models for RAG storage."""

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, computed_field


class DocumentStatus(str, Enum):
    """Document processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class DocumentModel(BaseModel):
    """A source document ingested into the system."""

    tenant_id: str = Field(..., description="Tenant this document belongs to")
    title: str = Field(..., description="Document title")
    source: str = Field(..., description="Source URI or file path")
    content: str = Field(default="", description="Full document content (markdown)")
    content_hash: str = Field(..., description="SHA256 hash of content for dedup")
    version: int = Field(default=1, description="Document version for re-ingestion")
    etag_or_commit: Optional[str] = Field(
        default=None, description="ETag or git commit for change detection"
    )
    status: DocumentStatus = Field(default=DocumentStatus.PENDING, description="Processing status")
    error_message: Optional[str] = Field(
        default=None, description="Error details if status is failed"
    )
    chunk_count: int = Field(default=0, description="Number of chunks created")
    metadata: dict = Field(default_factory=dict, description="Source-specific metadata")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @staticmethod
    def hash_content(content: str) -> str:
        """Generate SHA256 hash of document content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


class ChunkModel(BaseModel):
    """A chunk of a document with its embedding vector."""

    tenant_id: str = Field(..., description="Tenant this chunk belongs to")
    document_id: str = Field(..., description="Parent document ObjectId as string")
    chunk_id: str = Field(..., description="Stable deterministic ID for idempotent upserts")
    content: str = Field(..., description="Chunk text content")
    embedding: list[float] = Field(default_factory=list, description="Embedding vector")
    chunk_index: int = Field(..., description="Position within the source document")
    heading_path: list[str] = Field(
        default_factory=list, description="Heading hierarchy for context"
    )
    content_type: str = Field(default="text", description="Content type: text, code, table")
    lang: Optional[str] = Field(default=None, description="Language code if applicable")
    embedding_model: str = Field(
        default="text-embedding-3-small", description="Model used to generate embedding"
    )
    token_count: int = Field(default=0, description="Token count for this chunk")
    metadata: dict = Field(default_factory=dict, description="Chunk-level metadata")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @staticmethod
    def generate_chunk_id(source_uri: str, version: int, chunk_index: int, chunk_text: str) -> str:
        """Generate a stable chunk ID for idempotent upserts.

        chunk_id = SHA256(source_uri + version + chunk_index + chunk_text_hash)
        """
        chunk_text_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
        raw = f"{source_uri}|{version}|{chunk_index}|{chunk_text_hash}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_embedding(self) -> bool:
        """Whether this chunk has an embedding vector."""
        return len(self.embedding) > 0
