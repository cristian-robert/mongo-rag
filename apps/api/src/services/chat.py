"""Chat orchestration service shared by REST and WebSocket transports."""

import logging
from typing import Any, AsyncIterator, Optional

from src.core.dependencies import AgentDependencies
from src.models.api import SourceReference
from src.models.conversation import ChatMessage, MessageRole
from src.services.agent import create_rag_agent, format_search_context, run_search
from src.services.conversation import ConversationService

logger = logging.getLogger(__name__)


class ChatService:
    """Orchestrates the RAG chat flow: search, prompt, LLM, persistence."""

    def __init__(self, deps: AgentDependencies) -> None:
        self.deps = deps
        self.conversation_service = ConversationService(deps.conversations_collection)

    async def handle_message(
        self,
        message: str,
        tenant_id: str,
        conversation_id: Optional[str] = None,
        search_type: str = "hybrid",
    ) -> dict[str, Any]:
        """Handle a chat message and return the full response (non-streaming).

        Args:
            message: User's message text.
            tenant_id: Tenant ID for isolation.
            conversation_id: Existing conversation ID, or None for new.
            search_type: Search type to use.

        Returns:
            Dict with answer, sources, conversation_id.

        Raises:
            ValueError: If conversation_id belongs to a different tenant.
        """
        # Get or create conversation
        conv = await self.conversation_service.get_or_create(tenant_id, conversation_id)
        if conv is None:
            raise ValueError("Conversation not found")

        conv_id = str(conv["_id"])

        # Persist user message
        user_msg = ChatMessage(role=MessageRole.USER, content=message)
        await self.conversation_service.append_message(conv_id, tenant_id, user_msg)

        # Run search
        results = await run_search(self.deps, message, tenant_id, search_type=search_type)

        # Build context
        context = format_search_context(results)

        # Get conversation history for multi-turn
        history = await self.conversation_service.get_history(conv_id, tenant_id, limit=10)

        # Build messages for LLM
        history_text = ""
        if history and len(history) > 1:
            history_parts = []
            for msg in history[:-1]:  # Exclude the just-added user message
                role = msg.get("role", "user")
                content = msg.get("content", "")
                history_parts.append(f"{role}: {content}")
            history_text = "\n".join(history_parts)

        user_prompt = message
        if context and context != "No relevant documents found in the knowledge base.":
            user_prompt = f"Context from knowledge base:\n\n{context}\n\nUser question: {message}"
        if history_text:
            user_prompt = f"Conversation history:\n{history_text}\n\n{user_prompt}"

        # Call LLM
        agent = create_rag_agent()
        result = await agent.run(user_prompt)

        answer = result.output if hasattr(result, "output") else str(result.data)

        # Extract sources
        sources = [
            SourceReference(
                document_title=r.document_title,
                heading_path=r.metadata.get("heading_path", []),
                snippet=r.content[:200],
            )
            for r in results[:5]
        ]

        # Persist assistant message
        assistant_msg = ChatMessage(
            role=MessageRole.ASSISTANT,
            content=answer,
            sources=[s.document_title for s in sources],
        )
        await self.conversation_service.append_message(conv_id, tenant_id, assistant_msg)

        return {
            "answer": answer,
            "sources": sources,
            "conversation_id": conv_id,
        }

    async def handle_message_stream(
        self,
        message: str,
        tenant_id: str,
        conversation_id: Optional[str] = None,
        search_type: str = "hybrid",
    ) -> AsyncIterator[dict[str, Any]]:
        """Handle a chat message with streaming token output.

        Yields dicts with type: token|sources|done|error.

        Args:
            message: User's message text.
            tenant_id: Tenant ID for isolation.
            conversation_id: Existing conversation ID, or None for new.
            search_type: Search type to use.

        Yields:
            Event dicts: {"type": "token", "content": "..."} etc.
        """
        # Get or create conversation
        conv = await self.conversation_service.get_or_create(tenant_id, conversation_id)
        if conv is None:
            yield {"type": "error", "message": "Conversation not found"}
            return

        conv_id = str(conv["_id"])

        # Persist user message
        user_msg = ChatMessage(role=MessageRole.USER, content=message)
        await self.conversation_service.append_message(conv_id, tenant_id, user_msg)

        # Run search
        results = await run_search(self.deps, message, tenant_id, search_type=search_type)

        # Build context
        context = format_search_context(results)

        # Get conversation history
        history = await self.conversation_service.get_history(conv_id, tenant_id, limit=10)

        history_text = ""
        if history and len(history) > 1:
            history_parts = []
            for msg in history[:-1]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                history_parts.append(f"{role}: {content}")
            history_text = "\n".join(history_parts)

        user_prompt = message
        if context and context != "No relevant documents found in the knowledge base.":
            user_prompt = f"Context from knowledge base:\n\n{context}\n\nUser question: {message}"
        if history_text:
            user_prompt = f"Conversation history:\n{history_text}\n\n{user_prompt}"

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
            yield {"type": "error", "message": f"LLM error: {str(e)}"}
            return

        # Send sources
        sources = [
            SourceReference(
                document_title=r.document_title,
                heading_path=r.metadata.get("heading_path", []),
                snippet=r.content[:200],
            )
            for r in results[:5]
        ]
        yield {
            "type": "sources",
            "sources": [s.model_dump() for s in sources],
        }

        # Persist assistant message
        assistant_msg = ChatMessage(
            role=MessageRole.ASSISTANT,
            content=full_answer,
            sources=[s.document_title for s in sources],
        )
        await self.conversation_service.append_message(conv_id, tenant_id, assistant_msg)

        yield {"type": "done", "conversation_id": conv_id}
