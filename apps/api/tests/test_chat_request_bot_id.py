"""Tests for ChatRequest.bot_id field validation (#85)."""

import pytest
from pydantic import ValidationError

from src.models.api import ChatRequest


@pytest.mark.unit
def test_chat_request_accepts_no_bot_id():
    """bot_id is optional — omitting it must succeed."""
    req = ChatRequest(message="hello")
    assert req.bot_id is None


@pytest.mark.unit
def test_chat_request_accepts_valid_bot_id():
    """A 24-hex ObjectId-shaped string must be accepted."""
    req = ChatRequest(message="hello", bot_id="6543210abcdef0123456789a")
    assert req.bot_id == "6543210abcdef0123456789a"


@pytest.mark.unit
def test_chat_request_accepts_bot_id_under_max_length():
    """Anything up to 64 chars passes the length cap."""
    req = ChatRequest(message="hello", bot_id="x" * 64)
    assert req.bot_id == "x" * 64


@pytest.mark.unit
def test_chat_request_rejects_bot_id_over_max_length():
    """bot_id over 64 chars is rejected — defends ChatService from oversized lookups."""
    with pytest.raises(ValidationError):
        ChatRequest(message="hello", bot_id="x" * 65)


@pytest.mark.unit
def test_chat_request_rejects_unknown_extra_field():
    """StrictRequest still forbids unknown keys after we add bot_id."""
    with pytest.raises(ValidationError):
        ChatRequest(message="hello", not_a_field="x")
