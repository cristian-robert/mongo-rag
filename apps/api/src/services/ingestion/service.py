"""Tenant-aware ingestion service for API and Celery use."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pymongo.asynchronous.collection import AsyncCollection

from src.models.document import ChunkModel, DocumentStatus
from src.services.ingestion.chunker import DocumentChunk

logger = logging.getLogger(__name__)


class IngestionService:
    """Handles document and chunk persistence with tenant isolation."""

    def __init__(
        self,
        documents_collection: AsyncCollection,
        chunks_collection: AsyncCollection,
    ) -> None:
        self.documents = documents_collection
        self.chunks = chunks_collection

    async def create_pending_document(
        self,
        tenant_id: str,
        title: str,
        source: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Create a document record with pending status.

        Args:
            tenant_id: Tenant this document belongs to.
            title: Document title.
            source: Original filename or URI.
            metadata: Optional additional metadata.

        Returns:
            Inserted document ID as string.
        """
        now = datetime.now(timezone.utc)
        doc_id = str(uuid.uuid4())
        doc = {
            "_id": doc_id,
            "tenant_id": tenant_id,
            "title": title,
            "source": source,
            "content": "",
            "content_hash": "",
            "version": 1,
            "status": DocumentStatus.PENDING,
            "chunk_count": 0,
            "metadata": metadata or {},
            "created_at": now,
            "updated_at": now,
        }
        await self.documents.insert_one(doc)
        return doc_id

    async def update_status(
        self,
        document_id: str,
        tenant_id: str,
        status: str,
        error_message: Optional[str] = None,
        chunk_count: Optional[int] = None,
        content_hash: Optional[str] = None,
        version: Optional[int] = None,
        content: Optional[str] = None,
    ) -> None:
        """Update document processing status.

        Args:
            document_id: Document to update.
            tenant_id: Tenant ID for isolation.
            status: New status value.
            error_message: Error details if status is failed.
            chunk_count: Number of chunks created.
            content_hash: SHA256 hash of content.
            version: Document version.
            content: Full document content.
        """
        update: dict[str, Any] = {
            "$set": {
                "status": status,
                "updated_at": datetime.now(timezone.utc),
            }
        }
        if error_message is not None:
            update["$set"]["error_message"] = error_message
        if chunk_count is not None:
            update["$set"]["chunk_count"] = chunk_count
        if content_hash is not None:
            update["$set"]["content_hash"] = content_hash
        if version is not None:
            update["$set"]["version"] = version
        if content is not None:
            update["$set"]["content"] = content

        await self.documents.update_one(
            {"_id": document_id, "tenant_id": tenant_id},
            update,
        )

    async def check_duplicate(
        self,
        tenant_id: str,
        source: str,
        content_hash: str,
    ) -> Optional[str]:
        """Check if a document with the same content already exists.

        Args:
            tenant_id: Tenant to check within.
            source: Document source (filename or URI).
            content_hash: SHA256 hash of document content.

        Returns:
            Existing document ID if duplicate found, None otherwise.
        """
        existing = await self.documents.find_one(
            {
                "tenant_id": tenant_id,
                "source": source,
                "content_hash": content_hash,
                "status": DocumentStatus.READY,
            }
        )
        if existing:
            return existing["_id"]
        return None

    async def get_latest_version(self, tenant_id: str, source: str) -> int:
        """Get the latest version number for a document source.

        Args:
            tenant_id: Tenant to check within.
            source: Document source.

        Returns:
            Latest version number, or 0 if no previous version exists.
        """
        doc = await self.documents.find_one(
            {"tenant_id": tenant_id, "source": source},
            sort=[("version", -1)],
        )
        if doc:
            return doc.get("version", 1)
        return 0

    async def store_chunks(
        self,
        chunks: list[DocumentChunk],
        document_id: str,
        tenant_id: str,
        source: str,
        version: int,
        embedding_model: str,
    ) -> int:
        """Delete old chunks and insert new ones with tenant isolation.

        Args:
            chunks: Document chunks with embeddings.
            document_id: Parent document ID.
            tenant_id: Tenant ID for isolation.
            source: Document source for chunk ID generation.
            version: Document version for chunk ID generation.
            embedding_model: Name of the embedding model used.

        Returns:
            Number of chunks inserted.
        """
        # Delete existing chunks for this document
        await self.chunks.delete_many({"document_id": document_id, "tenant_id": tenant_id})

        if not chunks:
            return 0

        chunk_dicts = []
        for chunk in chunks:
            chunk_id = ChunkModel.generate_chunk_id(
                source_uri=source,
                version=version,
                chunk_index=chunk.index,
                chunk_text=chunk.content,
            )

            heading_path = chunk.metadata.get("heading_path", [])
            if isinstance(heading_path, str):
                heading_path = [heading_path]

            content_type = chunk.metadata.get("content_type", "text")

            chunk_dicts.append(
                {
                    "tenant_id": tenant_id,
                    "document_id": document_id,
                    "chunk_id": chunk_id,
                    "content": chunk.content,
                    "embedding": chunk.embedding,
                    "chunk_index": chunk.index,
                    "heading_path": heading_path,
                    "content_type": content_type,
                    "embedding_model": embedding_model,
                    "token_count": chunk.token_count or 0,
                    "metadata": chunk.metadata,
                    "created_at": datetime.now(timezone.utc),
                }
            )

        await self.chunks.insert_many(chunk_dicts, ordered=False)
        logger.info(
            "Stored %d chunks for document %s (tenant: %s)",
            len(chunk_dicts),
            document_id,
            tenant_id,
        )
        return len(chunk_dicts)

    async def get_document_status(
        self, document_id: str, tenant_id: str
    ) -> Optional[dict[str, Any]]:
        """Get document status for polling endpoint.

        Args:
            document_id: Document to check.
            tenant_id: Tenant ID for isolation.

        Returns:
            Dict with status fields, or None if not found.
        """
        doc = await self.documents.find_one(
            {"_id": document_id, "tenant_id": tenant_id},
            projection={
                "_id": 1,
                "status": 1,
                "chunk_count": 1,
                "version": 1,
                "error_message": 1,
                "title": 1,
            },
        )
        return doc
