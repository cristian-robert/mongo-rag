"""Tenant-aware ingestion service for API and Celery use."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import OperationFailure

from src.models.document import ChunkModel, DocumentStatus
from src.services.ingestion.chunker import DocumentChunk

logger = logging.getLogger(__name__)

# Fields exposed in API responses (whitelist — never leak content/embedding).
DOCUMENT_PROJECTION: dict[str, int] = {
    "_id": 1,
    "tenant_id": 1,
    "title": 1,
    "source": 1,
    "status": 1,
    "chunk_count": 1,
    "version": 1,
    "metadata": 1,
    "size_bytes": 1,
    "format": 1,
    "error_message": 1,
    "created_at": 1,
    "updated_at": 1,
}

ALLOWED_SORT_FIELDS = {"created_at", "updated_at", "title", "status"}


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
    ) -> Optional[dict[str, Any]]:
        """Check if a document with the same content already exists.

        Args:
            tenant_id: Tenant to check within.
            source: Document source (filename or URI).
            content_hash: SHA256 hash of document content.

        Returns:
            Existing document dict if duplicate found, None otherwise.
        """
        existing = await self.documents.find_one(
            {
                "tenant_id": tenant_id,
                "source": source,
                "content_hash": content_hash,
                "status": DocumentStatus.READY,
            },
            projection={"_id": 1, "chunk_count": 1, "version": 1},
        )
        return existing

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
                    "_id": chunk_id,
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

    # -- CRUD helpers --

    async def get_document(self, document_id: str, tenant_id: str) -> Optional[dict[str, Any]]:
        """Fetch a single document scoped by tenant_id.

        Returns the document dict (whitelisted projection) or None.
        Tenant_id is part of the filter so cross-tenant reads return None
        with the same shape as a true 404 — preventing enumeration.
        """
        return await self.documents.find_one(
            {"_id": document_id, "tenant_id": tenant_id},
            projection=DOCUMENT_PROJECTION,
        )

    async def list_documents(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        search: Optional[str] = None,
        sort: str = "created_at",
        order: str = "desc",
    ) -> tuple[list[dict[str, Any]], int]:
        """List documents for a tenant with pagination, filter and sort.

        Tenant_id is forced — never trusted from caller's filter dict.
        Returns (items, total).
        """
        filter_q: dict[str, Any] = {"tenant_id": tenant_id}
        if status:
            filter_q["status"] = status
        if search:
            # Escape regex meta and anchor case-insensitive prefix-friendly search
            escaped = _escape_regex(search)
            filter_q["title"] = {"$regex": escaped, "$options": "i"}

        sort_field = sort if sort in ALLOWED_SORT_FIELDS else "created_at"
        sort_dir = -1 if order == "desc" else 1
        # Tie-breaker on _id so paging is stable when sort field has ties.
        sort_spec: list[tuple[str, int]] = [(sort_field, sort_dir), ("_id", -1)]

        skip = max(0, (page - 1) * page_size)
        cursor = (
            self.documents.find(filter_q, projection=DOCUMENT_PROJECTION)
            .sort(sort_spec)
            .skip(skip)
            .limit(page_size)
        )
        items = [doc async for doc in cursor]
        total = await self.documents.count_documents(filter_q)
        return items, total

    async def update_metadata(
        self,
        document_id: str,
        tenant_id: str,
        title: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        """Update title and/or metadata on a document, tenant-scoped.

        Returns the updated document or None if not found.
        Refuses to update tenant_id, content, embeddings, status — those
        are owned by the ingestion pipeline.
        """
        update_set: dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
        if title is not None:
            update_set["title"] = title
        if metadata is not None:
            update_set["metadata"] = metadata

        if len(update_set) == 1:
            # Nothing user-provided — no-op, but still return current state.
            return await self.get_document(document_id, tenant_id)

        result = await self.documents.find_one_and_update(
            {"_id": document_id, "tenant_id": tenant_id},
            {"$set": update_set},
            projection=DOCUMENT_PROJECTION,
            return_document=True,  # return updated doc (ReturnDocument.AFTER == True)
        )
        return result

    async def delete_document_with_cascade(self, document_id: str, tenant_id: str) -> bool:
        """Atomically delete a document and all its chunks within a tenant.

        Tries a Mongo transaction first; falls back to sequenced deletes
        (chunks first, then document) for non-replica-set deployments.
        Returns True if a document was deleted, False if not found.
        """
        client = self.documents.database.client
        # Pre-flight: confirm doc exists for this tenant before touching chunks.
        doc = await self.documents.find_one(
            {"_id": document_id, "tenant_id": tenant_id},
            projection={"_id": 1},
        )
        if not doc:
            return False

        try:
            async with client.start_session() as session:

                async def _txn_body(s) -> int:
                    await self.chunks.delete_many(
                        {"document_id": document_id, "tenant_id": tenant_id},
                        session=s,
                    )
                    res = await self.documents.delete_one(
                        {"_id": document_id, "tenant_id": tenant_id},
                        session=s,
                    )
                    return res.deleted_count

                deleted_count = await session.with_transaction(_txn_body)
                return deleted_count == 1
        except OperationFailure as e:
            # Standalone Mongo (e.g. local dev) doesn't support transactions.
            # Fall back to sequenced deletes — chunks first so a mid-failure
            # leaves a stale doc (visible, recoverable) rather than orphan
            # chunks (invisible, undeletable via API).
            if _is_no_transaction_support(e):
                logger.info("transactions_unsupported_falling_back")
            else:
                logger.warning("transaction_delete_failed: %s", e)

            await self.chunks.delete_many({"document_id": document_id, "tenant_id": tenant_id})
            res = await self.documents.delete_one({"_id": document_id, "tenant_id": tenant_id})
            return res.deleted_count == 1

    async def bulk_delete_with_cascade(self, document_ids: Iterable[str], tenant_id: str) -> int:
        """Cascade-delete a batch of documents, tenant-scoped.

        Returns the number of documents actually deleted.
        Iterates per-id so a single failure can't corrupt others.
        """
        deleted = 0
        for doc_id in document_ids:
            if await self.delete_document_with_cascade(doc_id, tenant_id):
                deleted += 1
        return deleted

    async def mark_for_reingestion(
        self, document_id: str, tenant_id: str
    ) -> Optional[dict[str, Any]]:
        """Flip a document back to 'pending' for re-processing.

        Returns the updated document or None if not found.
        Does NOT touch chunks here — the worker will rebuild them.
        Refuses if the document is already in-flight (processing).
        """
        result = await self.documents.find_one_and_update(
            {
                "_id": document_id,
                "tenant_id": tenant_id,
                "status": {"$ne": DocumentStatus.PROCESSING.value},
            },
            {
                "$set": {
                    "status": DocumentStatus.PENDING.value,
                    "error_message": None,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            projection=DOCUMENT_PROJECTION,
            return_document=True,
        )
        return result


def _escape_regex(s: str) -> str:
    """Escape regex metacharacters for safe substring search."""
    import re

    return re.escape(s)


def _is_no_transaction_support(e: OperationFailure) -> bool:
    """Detect 'transactions require replica set' style errors."""
    msg = str(e).lower()
    return "transaction" in msg and (
        "replica" in msg or "not supported" in msg or "standalone" in msg
    )
