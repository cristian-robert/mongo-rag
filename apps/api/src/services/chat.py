"""Chat orchestration service shared by REST and WebSocket transports."""

import logging
from typing import Any, AsyncIterator, Optional

from src.core.dependencies import AgentDependencies
from src.models.api import Citation, RetrievalConfig, SourceReference
from src.models.conversation import ChatMessage, MessageRole
from src.models.search import SearchResult
from src.services.agent import create_rag_agent
from src.services.citations import build_citation_context, resolve_citations
from src.services.conversation import ConversationService
from src.services.retrieval import RetrievalOptions, RetrievalOutcome, retrieve

logger = logging.getLogger(__name__)


class ConversationNotFoundError(Exception):
    """Raised when a conversation_id does not exist or belongs to another tenant."""


class ChatService:
    """Orchestrates the RAG chat flow: search, prompt, LLM, persistence."""

    def __init__(self, deps: AgentDependencies) -> None:
        self.deps = deps
        self.conversation_service = ConversationService(deps.conversations_collection)

    @staticmethod
    def _build_options(
        search_type: str,
        retrieval: Optional[RetrievalConfig],
    ) -> RetrievalOptions:
        if retrieval is None:
            return RetrievalOptions(search_type=search_type)
        return RetrievalOptions(
            search_type=search_type,
            match_count=retrieval.match_count,
            rrf_k=retrieval.rrf_k,
            rerank=retrieval.rerank,
            rerank_top_n=retrieval.rerank_top_n,
            query_rewrite=retrieval.query_rewrite,
        )

    async def _prepare_chat(
        self,
        message: str,
        tenant_id: str,
        conversation_id: Optional[str],
        search_type: str,
        retrieval: Optional[RetrievalConfig] = None,
    ) -> tuple[str, str, RetrievalOutcome]:
        """Shared setup: conversation, retrieval, prompt construction.

        Returns:
            Tuple of (conv_id, user_prompt, retrieval_outcome).

        Raises:
            ConversationNotFoundError: If conversation_id belongs to a different tenant.
        """
        # Get or create conversation
        conv = await self.conversation_service.get_or_create(tenant_id, conversation_id)
        if conv is None:
            raise ConversationNotFoundError("Conversation not found")

        conv_id = str(conv["_id"])

        # Persist user message
        user_msg = ChatMessage(role=MessageRole.USER, content=message)
        await self.conversation_service.append_message(conv_id, tenant_id, user_msg)

        # Run retrieval pipeline (rewrite + hybrid + RRF + optional rerank)
        options = self._build_options(search_type, retrieval)
        outcome = await retrieve(self.deps, message, tenant_id, options)

        # Build numbered citation context (plain text, no XML/JSON markup)
        context = build_citation_context(outcome.results)

        # Get conversation history for multi-turn
        history = await self.conversation_service.get_history(conv_id, tenant_id, limit=10)

        # Build history text
        history_text = ""
        if history and len(history) > 1:
            history_parts = []
            for msg in history[:-1]:  # Exclude the just-added user message
                role = msg.get("role", "user")
                content = msg.get("content", "")
                history_parts.append(f"{role}: {content}")
            history_text = "\n".join(history_parts)

        # Assemble user prompt. Sources are presented as "[n] title — heading\nbody"
        # blocks separated by ``---``. The system prompt instructs the model to
        # cite using matching ``[n]`` markers.
        user_prompt = message
        if context and context != "No relevant documents found in the knowledge base.":
            user_prompt = (
                "Sources (numbered — cite with [1], [2], etc.):\n\n"
                f"{context}\n\nUser question: {message}"
            )
        if history_text:
            user_prompt = f"Conversation history:\n{history_text}\n\n{user_prompt}"

        return conv_id, user_prompt, outcome

    def _extract_sources(self, results: list[SearchResult]) -> list[SourceReference]:
        """Extract source references (legacy field, retained for compatibility)."""
        return [
            SourceReference(
                document_title=r.document_title,
                heading_path=r.metadata.get("heading_path", []),
                snippet=r.content[:200],
            )
            for r in results[:5]
        ]

    async def _persist_assistant_message(
        self,
        conv_id: str,
        tenant_id: str,
        answer: str,
        sources: list[SourceReference],
    ) -> None:
        """Persist the assistant's response to the conversation."""
        assistant_msg = ChatMessage(
            role=MessageRole.ASSISTANT,
            content=answer,
            sources=[s.document_title for s in sources],
        )
        await self.conversation_service.append_message(conv_id, tenant_id, assistant_msg)

    async def handle_message(
        self,
        message: str,
        tenant_id: str,
        conversation_id: Optional[str] = None,
        search_type: str = "hybrid",
        retrieval: Optional[RetrievalConfig] = None,
    ) -> dict[str, Any]:
        """Handle a chat message and return the full response (non-streaming).

        Returns:
            Dict with answer, sources, citations, conversation_id, rewritten_queries.
        """
        conv_id, user_prompt, outcome = await self._prepare_chat(
            message, tenant_id, conversation_id, search_type, retrieval
        )

        # Call LLM
        agent = create_rag_agent()
        result = await agent.run(user_prompt)
        answer = str(result.output)

        # Resolve [n] markers → Citation objects
        citations: list[Citation] = resolve_citations(answer, outcome.results)

        # Extract sources and persist
        sources = self._extract_sources(outcome.results)
        await self._persist_assistant_message(conv_id, tenant_id, answer, sources)

        return {
            "answer": answer,
            "sources": sources,
            "citations": citations,
            "conversation_id": conv_id,
            "rewritten_queries": outcome.rewritten_queries,
        }

    async def handle_message_stream(
        self,
        message: str,
        tenant_id: str,
        conversation_id: Optional[str] = None,
        search_type: str = "hybrid",
        retrieval: Optional[RetrievalConfig] = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Handle a chat message with streaming token output.

        Yields dicts with type: token|sources|citations|done|error.
        """
        try:
            conv_id, user_prompt, outcome = await self._prepare_chat(
                message, tenant_id, conversation_id, search_type, retrieval
            )
        except ConversationNotFoundError:
            yield {"type": "error", "message": "Conversation not found"}
            return

        # Stream LLM response
        agent = create_rag_agent()
        full_answer = ""

        try:
            async with agent.run_stream(user_prompt) as stream:
                async for text in stream.stream_text(delta=True):
                    full_answer += text
                    yield {"type": "token", "content": text}
        except Exception as e:
            logger.exception("LLM streaming error: %s", str(e))
            yield {"type": "error", "message": "Failed to generate response"}
            return

        # Resolve citations from the completed answer
        citations = resolve_citations(full_answer, outcome.results)
        sources = self._extract_sources(outcome.results)

        yield {
            "type": "sources",
            "sources": [s.model_dump() for s in sources],
        }
        yield {
            "type": "citations",
            "citations": [c.model_dump() for c in citations],
        }
        if outcome.rewritten_queries:
            yield {
                "type": "rewritten_queries",
                "queries": outcome.rewritten_queries,
            }

        await self._persist_assistant_message(conv_id, tenant_id, full_answer, sources)

        yield {"type": "done", "conversation_id": conv_id}
