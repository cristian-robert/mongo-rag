"""Tests for ChatService bot resolution and prompt composition (#85)."""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

from src.services.chat import BotNotFoundError, ChatService


def _mk_bot(
    *,
    bot_id: ObjectId | None = None,
    tenant_id: str = "tenant-abc",
    system_prompt: str = "You are a pirate. Speak in pirate.",
    name: str = "Pirate Bot",
    tone: str = "playful",
    document_filter: dict | None = None,
) -> dict[str, Any]:
    """Build a bot doc that mirrors what BotService.get returns."""
    now = datetime.now(timezone.utc)
    return {
        "id": str(bot_id or ObjectId()),
        "tenant_id": tenant_id,
        "name": name,
        "slug": name.lower().replace(" ", "-"),
        "description": None,
        "system_prompt": system_prompt,
        "welcome_message": "Hi",
        "tone": tone,
        "is_public": False,
        "model_config": {"temperature": 0.2, "max_tokens": 1024},
        "widget_config": {
            "primary_color": "#0f172a",
            "position": "bottom-right",
            "avatar_url": None,
        },
        "document_filter": document_filter or {"mode": "all", "document_ids": []},
        "created_at": now,
        "updated_at": now,
    }


def _mk_deps() -> MagicMock:
    deps = MagicMock()
    deps.settings = MagicMock()
    deps.settings.default_match_count = 5
    deps.settings.max_match_count = 50
    deps.bots_collection = MagicMock()
    deps.conversations_collection = MagicMock()
    return deps


@pytest.fixture
def patched_chat_service():
    """ChatService with conversation + retrieval stubbed; bot service patched per-test."""
    deps = _mk_deps()
    service = ChatService(deps)

    # Stub conversation persistence — keep tests focused on bot/prompt path.
    service.conversation_service = MagicMock()
    service.conversation_service.get_or_create = AsyncMock(
        return_value={"_id": ObjectId(), "tenant_id": "tenant-abc"}
    )
    service.conversation_service.append_message = AsyncMock()
    service.conversation_service.get_history = AsyncMock(return_value=[])
    return service, deps


# --- _resolve_bot ---------------------------------------------------------


@pytest.mark.unit
async def test_resolve_bot_returns_none_when_bot_id_is_none(patched_chat_service):
    service, _ = patched_chat_service
    bot = await service._resolve_bot(None, "tenant-abc")
    assert bot is None


@pytest.mark.unit
async def test_resolve_bot_returns_bot_dict_for_owning_tenant(patched_chat_service):
    service, _ = patched_chat_service
    expected = _mk_bot()
    with patch("src.services.chat.BotService") as bot_svc_cls:
        bot_svc = MagicMock()
        bot_svc.get = AsyncMock(return_value=expected)
        bot_svc_cls.return_value = bot_svc

        result = await service._resolve_bot("bot-123", "tenant-abc")
        assert result == expected
        bot_svc.get.assert_awaited_once_with("bot-123", "tenant-abc")


@pytest.mark.unit
async def test_resolve_bot_raises_for_cross_tenant_lookup(patched_chat_service):
    """BotService.get returns None for cross-tenant — raise BotNotFoundError."""
    service, _ = patched_chat_service
    with patch("src.services.chat.BotService") as bot_svc_cls:
        bot_svc = MagicMock()
        bot_svc.get = AsyncMock(return_value=None)
        bot_svc_cls.return_value = bot_svc

        with pytest.raises(BotNotFoundError):
            await service._resolve_bot("foreign-bot", "tenant-abc")


# --- _compose_system_prompt ----------------------------------------------


@pytest.mark.unit
def test_compose_system_prompt_uses_bot_system_prompt_verbatim(patched_chat_service):
    service, _ = patched_chat_service
    bot = _mk_bot(system_prompt="ABSOLUTELY UNIQUE SENTINEL", name="Acme")
    prompt = service._compose_system_prompt(bot)
    assert prompt == "ABSOLUTELY UNIQUE SENTINEL"
    # No leakage of build_system_prompt template content
    assert "documentation assistant" not in prompt.lower()


@pytest.mark.unit
def test_compose_system_prompt_falls_back_when_bot_prompt_blank(patched_chat_service):
    """If a bot has empty/whitespace system_prompt, fall back to the template."""
    service, _ = patched_chat_service
    bot = _mk_bot(system_prompt="   ", name="Acme Widgets", tone="professional")
    prompt = service._compose_system_prompt(bot)
    assert "Acme Widgets" in prompt
    # Default template wording must be present in the fallback path.
    assert "documentation assistant" in prompt.lower()


@pytest.mark.unit
def test_compose_system_prompt_appends_tone_suffix_when_falling_back(patched_chat_service):
    service, _ = patched_chat_service
    bot = _mk_bot(system_prompt="", tone="playful", name="Acme")
    prompt = service._compose_system_prompt(bot)
    # Tone suffix is appended to the base template only on fallback.
    assert prompt.endswith(prompt.rstrip())  # trailing whitespace trimmed
    # The playful suffix mentions playfulness in some form — keep the
    # contract loose so we can refine wording without breaking the test.
    assert "playful" in prompt.lower() or "fun" in prompt.lower()


# --- handle_message integration ------------------------------------------


@pytest.mark.unit
async def test_handle_message_uses_bot_prompt_for_resolved_bot(patched_chat_service):
    """End-to-end: bot_id → custom system_prompt reaches create_rag_agent."""
    service, _ = patched_chat_service

    captured: dict[str, Any] = {}

    def fake_create_agent(system_prompt=None, product_name="this product"):
        captured["system_prompt"] = system_prompt
        captured["product_name"] = product_name
        agent = MagicMock()
        run_result = MagicMock()
        run_result.output = "answer"
        agent.run = AsyncMock(return_value=run_result)
        return agent

    bot = _mk_bot(system_prompt="You are a pirate.", name="Acme Bot")
    with (
        patch(
            "src.services.chat.retrieve",
            new=AsyncMock(
                return_value=MagicMock(results=[], rewritten_queries=[]),
            ),
        ),
        patch("src.services.chat.create_rag_agent", side_effect=fake_create_agent),
        patch("src.services.chat.BotService") as bot_svc_cls,
    ):
        bot_svc = MagicMock()
        bot_svc.get = AsyncMock(return_value=bot)
        bot_svc_cls.return_value = bot_svc

        await service.handle_message(
            message="hi",
            tenant_id="tenant-abc",
            bot_id="bot-123",
        )

    assert captured["system_prompt"] == "You are a pirate."
    assert captured["product_name"] == "Acme Bot"


@pytest.mark.unit
async def test_handle_message_without_bot_id_uses_default_agent(patched_chat_service):
    service, _ = patched_chat_service

    captured: dict[str, Any] = {}

    def fake_create_agent(system_prompt=None, product_name="this product"):
        captured["system_prompt"] = system_prompt
        captured["product_name"] = product_name
        agent = MagicMock()
        run_result = MagicMock()
        run_result.output = "answer"
        agent.run = AsyncMock(return_value=run_result)
        return agent

    with (
        patch(
            "src.services.chat.retrieve",
            new=AsyncMock(
                return_value=MagicMock(results=[], rewritten_queries=[]),
            ),
        ),
        patch("src.services.chat.create_rag_agent", side_effect=fake_create_agent),
    ):
        await service.handle_message(message="hi", tenant_id="tenant-abc")

    # No bot → no overrides; default agent path.
    assert captured["system_prompt"] is None
    assert captured["product_name"] == "this product"


@pytest.mark.unit
async def test_handle_message_propagates_document_filter(patched_chat_service):
    """document_filter.mode=='ids' → retrieve() is called with those document_ids."""
    service, _ = patched_chat_service

    captured: dict[str, Any] = {}

    async def fake_retrieve(deps, query, tenant_id, options):
        captured["document_ids"] = options.document_ids
        return MagicMock(results=[], rewritten_queries=[])

    bot = _mk_bot(
        document_filter={"mode": "ids", "document_ids": ["doc-1", "doc-2"]},
    )
    with (
        patch("src.services.chat.retrieve", new=fake_retrieve),
        patch("src.services.chat.create_rag_agent") as create_agent,
        patch("src.services.chat.BotService") as bot_svc_cls,
    ):
        agent = MagicMock()
        run_result = MagicMock()
        run_result.output = "answer"
        agent.run = AsyncMock(return_value=run_result)
        create_agent.return_value = agent

        bot_svc = MagicMock()
        bot_svc.get = AsyncMock(return_value=bot)
        bot_svc_cls.return_value = bot_svc

        await service.handle_message(message="hi", tenant_id="tenant-abc", bot_id="bot-123")

    assert captured["document_ids"] == ("doc-1", "doc-2")


@pytest.mark.unit
async def test_handle_message_ignores_document_filter_when_mode_all(patched_chat_service):
    service, _ = patched_chat_service
    captured: dict[str, Any] = {}

    async def fake_retrieve(deps, query, tenant_id, options):
        captured["document_ids"] = options.document_ids
        return MagicMock(results=[], rewritten_queries=[])

    bot = _mk_bot(document_filter={"mode": "all", "document_ids": []})
    with (
        patch("src.services.chat.retrieve", new=fake_retrieve),
        patch("src.services.chat.create_rag_agent") as create_agent,
        patch("src.services.chat.BotService") as bot_svc_cls,
    ):
        agent = MagicMock()
        run_result = MagicMock()
        run_result.output = "answer"
        agent.run = AsyncMock(return_value=run_result)
        create_agent.return_value = agent

        bot_svc = MagicMock()
        bot_svc.get = AsyncMock(return_value=bot)
        bot_svc_cls.return_value = bot_svc

        await service.handle_message(message="hi", tenant_id="tenant-abc", bot_id="bot-123")

    assert captured["document_ids"] is None


@pytest.mark.unit
async def test_handle_message_raises_bot_not_found_for_unknown_bot_id(patched_chat_service):
    service, _ = patched_chat_service
    with patch("src.services.chat.BotService") as bot_svc_cls:
        bot_svc = MagicMock()
        bot_svc.get = AsyncMock(return_value=None)
        bot_svc_cls.return_value = bot_svc

        with pytest.raises(BotNotFoundError):
            await service.handle_message(
                message="hi",
                tenant_id="tenant-abc",
                bot_id="bot-i-dont-own",
            )


@pytest.mark.unit
async def test_handle_message_does_not_log_system_prompt(caplog, patched_chat_service):
    """Security: a bot's system_prompt must never appear in any log line."""
    import logging

    service, _ = patched_chat_service
    secret = "TOP-SECRET-CUSTOMER-INSTRUCTIONS-XYZZY"
    bot = _mk_bot(system_prompt=secret)

    with (
        patch(
            "src.services.chat.retrieve",
            new=AsyncMock(return_value=MagicMock(results=[], rewritten_queries=[])),
        ),
        patch("src.services.chat.create_rag_agent") as create_agent,
        patch("src.services.chat.BotService") as bot_svc_cls,
    ):
        agent = MagicMock()
        run_result = MagicMock()
        run_result.output = "answer"
        agent.run = AsyncMock(return_value=run_result)
        create_agent.return_value = agent

        bot_svc = MagicMock()
        bot_svc.get = AsyncMock(return_value=bot)
        bot_svc_cls.return_value = bot_svc

        with caplog.at_level(logging.DEBUG):
            await service.handle_message(message="hi", tenant_id="tenant-abc", bot_id="bot-123")

    blob = "\n".join(r.getMessage() + " " + str(r.args or "") for r in caplog.records)
    assert secret not in blob


# --- streaming path ------------------------------------------------------


@pytest.mark.unit
async def test_handle_message_stream_uses_bot_prompt(patched_chat_service):
    """Streaming path must honor the bot's system_prompt the same way."""
    import asyncio
    import contextlib

    service, _ = patched_chat_service
    captured: dict[str, Any] = {}

    def fake_create_agent(system_prompt=None, product_name="this product"):
        captured["system_prompt"] = system_prompt
        captured["product_name"] = product_name
        agent = MagicMock()

        @contextlib.asynccontextmanager
        async def fake_stream(prompt):
            stream = MagicMock()

            async def stream_text(delta=False):
                yield "answer"
                await asyncio.sleep(0)

            stream.stream_text = stream_text
            yield stream

        agent.run_stream = fake_stream
        return agent

    bot = _mk_bot(system_prompt="You are a parrot.", name="Acme")
    with (
        patch(
            "src.services.chat.retrieve",
            new=AsyncMock(
                return_value=MagicMock(results=[], rewritten_queries=[]),
            ),
        ),
        patch("src.services.chat.create_rag_agent", side_effect=fake_create_agent),
        patch("src.services.chat.BotService") as bot_svc_cls,
    ):
        bot_svc = MagicMock()
        bot_svc.get = AsyncMock(return_value=bot)
        bot_svc_cls.return_value = bot_svc

        events = [
            event
            async for event in service.handle_message_stream(
                message="hi",
                tenant_id="tenant-abc",
                bot_id="bot-123",
            )
        ]

    assert captured["system_prompt"] == "You are a parrot."
    assert any(e.get("type") == "done" for e in events)
