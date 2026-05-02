"""Tests for the RAG agent factory (#85)."""

from unittest.mock import MagicMock, patch

import pytest

from src.services.agent import create_rag_agent


@pytest.mark.unit
def test_create_rag_agent_falls_back_to_default_prompt():
    """No args → uses build_system_prompt('this product')."""
    with (
        patch("src.services.agent.get_llm_model", return_value=MagicMock()),
        patch("src.services.agent.Agent") as agent_cls,
    ):
        create_rag_agent()
        kwargs = agent_cls.call_args.kwargs
        # The default template includes the product placeholder text.
        assert "this product" in kwargs["system_prompt"]


@pytest.mark.unit
def test_create_rag_agent_uses_explicit_system_prompt():
    """When system_prompt is supplied, it is the agent's prompt verbatim."""
    custom = "You are a pirate. Speak in pirate."
    with (
        patch("src.services.agent.get_llm_model", return_value=MagicMock()),
        patch("src.services.agent.Agent") as agent_cls,
    ):
        create_rag_agent(system_prompt=custom)
        kwargs = agent_cls.call_args.kwargs
        assert kwargs["system_prompt"] == custom


@pytest.mark.unit
def test_create_rag_agent_uses_product_name_when_no_system_prompt():
    """product_name flows into build_system_prompt when system_prompt omitted."""
    with (
        patch("src.services.agent.get_llm_model", return_value=MagicMock()),
        patch("src.services.agent.Agent") as agent_cls,
    ):
        create_rag_agent(product_name="Acme Widgets")
        kwargs = agent_cls.call_args.kwargs
        assert "Acme Widgets" in kwargs["system_prompt"]


@pytest.mark.unit
def test_create_rag_agent_system_prompt_overrides_product_name():
    """When both are set, system_prompt wins outright (no product_name leak)."""
    custom = "You are a parrot. Repeat user messages."
    with (
        patch("src.services.agent.get_llm_model", return_value=MagicMock()),
        patch("src.services.agent.Agent") as agent_cls,
    ):
        create_rag_agent(system_prompt=custom, product_name="Acme")
        kwargs = agent_cls.call_args.kwargs
        assert kwargs["system_prompt"] == custom
        assert "Acme" not in kwargs["system_prompt"]
