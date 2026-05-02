"""Chat orchestration service shared by REST and WebSocket transports."""

import logging
from typing import Any, AsyncIterator, Optional

from src.core.dependencies import AgentDependencies
from src.core.prompts import build_system_prompt
from src.models.api import Citation, RetrievalConfig, SourceReference
from src.models.conversation import ChatMessage, MessageRole
from src.models.search import SearchResult
from src.services.agent import create_rag_agent
from src.services.bot import BotService
from src.services.citations import build_citation_context, resolve_citations
from src.services.conversation import ConversationService
from src.services.retrieval import RetrievalOptions, RetrievalOutcome, retrieve

logger = logging.getLogger(__name__)


# Tone → system-prompt suffix. Consulted only on the fallback path
# (bot exists but its system_prompt is blank). The persisted bot model
# requires system_prompt (min_length=10) so this is forward-compat
# scaffolding rather than a today path. Kept short and explicit to match
# the BotTone literal in models/bot.py.
_TONE_SUFFIXES: dict[str, str] = {
    "professional": "",
    "friendly": "Adopt a warm, approachable tone. Use plain language.",
    "concise": "Keep answers short. Prefer single-paragraph or bullet replies.",
    "technical": (
        "Use precise technical terminology. Include code or config snippets when "
        "they materially aid the answer."
    ),
    "playful": (
        "Be playful and fun, but never at the expense of accuracy. A light touch of "
        "humor is welcome; jokes never replace correct information."
    ),
}


class ConversationNotFoundError(Exception):
    """Raised when a conversation_id does not exist or belongs to another tenant."""


class BotNotFoundError(Exception):
    """Raised when a bot_id does not exist or belongs to another tenant.

    The two cases collapse into one error on purpose — leaking which case
    applied would tell an attacker whether a bot_id exists in some other
    tenant, which is itself a tenant-isolation leak.
    """


class ChatService:
    """Orchestrates the RAG chat flow: search, prompt, LLM, persistence."""

    def __init__(self, deps: AgentDependencies) -> None:
        self.deps = deps
        self.conversation_service = ConversationService(deps.conversations_collection)

    @staticmethod
    def _build_options(
        search_type: str,
        retrieval: Optional[RetrievalConfig],
        document_ids: Optional[tuple[str, ...]] = None,
    ) -> RetrievalOptions:
        if retrieval is None:
            return RetrievalOptions(
                search_type=search_type,
                document_ids=document_ids,
            )
        return RetrievalOptions(
            search_type=search_type,
            match_count=retrieval.match_count,
            rrf_k=retrieval.rrf_k,
            rerank=retrieval.rerank,
            rerank_top_n=retrieval.rerank_top_n,
            query_rewrite=retrieval.query_rewrite,
            document_ids=document_ids,
        )

    async def _resolve_bot(
        self,
        bot_id: Optional[str],
        tenant_id: str,
    ) -> Optional[dict[str, Any]]:
        """Resolve a bot_id to its config dict, scoped to ``tenant_id``.

        ``BotService.get`` already enforces tenant isolation at the Mongo
        filter level. We treat "not found" and "wrong tenant" identically
        — see ``BotNotFoundError`` for why we don't differentiate.

        Returns ``None`` when ``bot_id`` is itself ``None`` (legacy /
        no-bot callers); raises ``BotNotFoundError`` when a bot_id was
        supplied but cannot be resolved.
        """
        if bot_id is None:
            return None
        bot_service = BotService(self.deps.bots_collection)
        bot = await bot_service.get(bot_id, tenant_id)
        if bot is None:
            logger.info(
                "chat_bot_not_found",
                extra={"bot_id": bot_id, "tenant_id": tenant_id},
            )
            raise BotNotFoundError("Bot not found")
        # Never log system_prompt — it can contain customer-sensitive
        # instructions. Log only opaque metadata.
        logger.info(
            "chat_bot_resolved",
            extra={
                "bot_id": bot_id,
                "tenant_id": tenant_id,
                "doc_filter_mode": bot.get("document_filter", {}).get("mode", "all"),
            },
        )
        return bot

    @staticmethod
    def _compose_system_prompt(bot: dict[str, Any]) -> str:
        """Build the agent's system prompt from a resolved bot doc.

        Order:
          1. ``bot.system_prompt`` — used verbatim when present (after
             trim). This is the primary path because the persisted model
             requires ``system_prompt``.
          2. Fallback: ``build_system_prompt(bot.name)`` + tone suffix.
             The tone suffix is appended only on the fallback so a
             bot's hand-authored prompt is never silently augmented.
        """
        sp = (bot.get("system_prompt") or "").strip()
        if sp:
            return sp

        product = (bot.get("name") or "").strip() or "this product"
        base = build_system_prompt(product)
        suffix = _TONE_SUFFIXES.get(bot.get("tone") or "professional", "")
        if suffix:
            return f"{base.rstrip()}\n\n{suffix}".rstrip()
        return base.rstrip()

    @staticmethod
    def _document_ids_from_bot(bot: Optional[dict[str, Any]]) -> Optional[tuple[str, ...]]:
        """Extract a document_ids tuple from the bot's document_filter, if any.

        Returns ``None`` when the bot is absent, ``mode != "ids"``, or the
        list is empty (treated as "no restriction" — consistent with how
        BotService stores the default DocumentFilter).
        """
        if bot is None:
            return None
        df = bot.get("document_filter") or {}
        if df.get("mode") != "ids":
            return None
        ids = df.get("document_ids") or []
        if not ids:
            return None
        return tuple(ids)

    async def _prepare_chat(
        self,
        message: str,
        tenant_id: str,
        conversation_id: Optional[str],
        search_type: str,
        retrieval: Optional[RetrievalConfig] = None,
        bot: Optional[dict[str, Any]] = None,
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

        # Run retrieval pipeline (rewrite + hybrid + RRF + optional rerank).
        # Bot's document_filter narrows retrieval to a whitelist when set.
        document_ids = self._document_ids_from_bot(bot)
        options = self._build_options(search_type, retrieval, document_ids=document_ids)
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

    def _build_agent_for(self, bot: Optional[dict[str, Any]]):
        """Build the LLM agent for this turn, honoring the bot config if any.

        Returns the agent the chat service will invoke. Centralised so the
        streaming and non-streaming paths can't drift apart.
        """
        if bot is None:
            return create_rag_agent()
        system_prompt = self._compose_system_prompt(bot)
        product_name = (bot.get("name") or "").strip() or "this product"
        return create_rag_agent(system_prompt=system_prompt, product_name=product_name)

    async def handle_message(
        self,
        message: str,
        tenant_id: str,
        conversation_id: Optional[str] = None,
        search_type: str = "hybrid",
        retrieval: Optional[RetrievalConfig] = None,
        bot_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Handle a chat message and return the full response (non-streaming).

        Returns:
            Dict with answer, sources, citations, conversation_id, rewritten_queries.

        Raises:
            ConversationNotFoundError: when conversation_id belongs to another tenant.
            BotNotFoundError: when bot_id is supplied and cannot be resolved
                (unknown id OR cross-tenant).
        """
        bot = await self._resolve_bot(bot_id, tenant_id)
        conv_id, user_prompt, outcome = await self._prepare_chat(
            message, tenant_id, conversation_id, search_type, retrieval, bot=bot
        )

        # Call LLM with the bot-aware agent.
        agent = self._build_agent_for(bot)
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
        bot_id: Optional[str] = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Handle a chat message with streaming token output.

        Yields dicts with type: token|sources|citations|done|error.

        BotNotFoundError surfaces as an ``error`` event so the SSE / WS
        consumer can render a user-facing message — same shape as the
        existing ConversationNotFoundError handling.
        """
        try:
            bot = await self._resolve_bot(bot_id, tenant_id)
        except BotNotFoundError:
            yield {"type": "error", "message": "Bot not found"}
            return

        try:
            conv_id, user_prompt, outcome = await self._prepare_chat(
                message, tenant_id, conversation_id, search_type, retrieval, bot=bot
            )
        except ConversationNotFoundError:
            yield {"type": "error", "message": "Conversation not found"}
            return

        # Stream LLM response
        agent = self._build_agent_for(bot)
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
