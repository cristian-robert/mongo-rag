"""Unit tests for the AnalyticsService aggregation logic."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.analytics import (
    DEFAULT_WINDOW_DAYS,
    MAX_WINDOW_DAYS,
    AnalyticsService,
)


def _aggregate_cursor(value):
    """Helper: build a MagicMock matching async aggregate().to_list()."""
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=value)
    coll = MagicMock()
    coll.aggregate = AsyncMock(return_value=cursor)
    return coll, cursor


@pytest.mark.unit
async def test_overview_aggregates_facet_results():
    facet = [
        {
            "totals": [{"_id": None, "conversations": 4, "sessions": ["s1", "s2", "s3"]}],
            "messages": [
                {"_id": "user", "count": 12, "avg_chars": 24.0, "no_answer": 0},
                {"_id": "assistant", "count": 12, "avg_chars": 380.5, "no_answer": 3},
            ],
            "top_queries": [
                {"_id": "what is rag", "count": 4},
                {"_id": "pricing", "count": 2},
            ],
        }
    ]
    coll, _ = _aggregate_cursor(facet)
    service = AnalyticsService(coll)

    overview = await service.overview("tenant-1", window_days=14)

    assert overview.window_days == 14
    assert overview.total_conversations == 4
    assert overview.unique_sessions == 3
    assert overview.total_user_queries == 12
    assert overview.total_assistant_responses == 12
    assert overview.total_messages == 24
    assert overview.no_answer_count == 3
    assert overview.no_answer_rate == 0.25
    assert overview.avg_response_chars == 380.5
    assert overview.top_queries[0].query == "what is rag"
    assert overview.top_queries[0].count == 4

    # Tenant must always be in the match clause.
    pipeline = coll.aggregate.call_args[0][0]
    assert pipeline[0]["$match"]["tenant_id"] == "tenant-1"


@pytest.mark.unit
async def test_overview_handles_no_data():
    coll, _ = _aggregate_cursor([{"totals": [], "messages": [], "top_queries": []}])
    service = AnalyticsService(coll)

    overview = await service.overview("tenant-empty")

    assert overview.total_conversations == 0
    assert overview.total_messages == 0
    assert overview.no_answer_rate == 0.0
    assert overview.top_queries == []


@pytest.mark.unit
async def test_window_clamped_to_max():
    coll, _ = _aggregate_cursor([{"totals": [], "messages": [], "top_queries": []}])
    service = AnalyticsService(coll)

    overview = await service.overview("tenant-1", window_days=10_000)

    assert overview.window_days == MAX_WINDOW_DAYS


@pytest.mark.unit
async def test_window_defaults_when_none():
    coll, _ = _aggregate_cursor([{"totals": [], "messages": [], "top_queries": []}])
    service = AnalyticsService(coll)

    overview = await service.overview("tenant-1", window_days=None)

    assert overview.window_days == DEFAULT_WINDOW_DAYS


@pytest.mark.unit
async def test_timeseries_densifies_window():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = [
        {"_id": {"date": today, "role": "user"}, "count": 3},
        {"_id": {"date": today, "role": "assistant"}, "count": 3},
    ]
    coll, _ = _aggregate_cursor(rows)
    service = AnalyticsService(coll)

    ts = await service.timeseries("tenant-1", window_days=5)

    # 5-day window — densified inclusively, expect 6 buckets (start..end).
    assert len(ts.points) == 6
    today_point = next(p for p in ts.points if p.date == today)
    assert today_point.user_queries == 3
    assert today_point.assistant_responses == 3
    # Earlier days should be zero-filled.
    assert all(p.user_queries >= 0 for p in ts.points)


@pytest.mark.unit
async def test_queries_filters_to_user_messages_with_pairing():
    now = datetime.now(timezone.utc)
    facet = [
        {
            "items": [
                {
                    "conversation_id": "c1",
                    "session_id": "s1",
                    "query": "What is RAG?",
                    "timestamp": now,
                    "answer_preview": "Retrieval augmented generation...",
                    "sources_count": 2,
                    "no_answer": False,
                },
                {
                    "conversation_id": "c2",
                    "session_id": "s2",
                    "query": "How do I export data?",
                    "timestamp": now - timedelta(hours=1),
                    "answer_preview": "I do not know.",
                    "sources_count": 0,
                    "no_answer": True,
                },
            ],
            "total": [{"n": 27}],
        }
    ]
    coll, _ = _aggregate_cursor(facet)
    service = AnalyticsService(coll)

    page = await service.queries("tenant-1", window_days=30, page=1, page_size=25)

    assert page.total == 27
    assert len(page.items) == 2
    assert page.items[0].query == "What is RAG?"
    assert page.items[1].no_answer is True
    assert page.has_more is True


@pytest.mark.unit
async def test_queries_no_answer_filter_appends_match():
    coll, _ = _aggregate_cursor([{"items": [], "total": []}])
    service = AnalyticsService(coll)

    await service.queries("tenant-1", no_answer_only=True)

    pipeline = coll.aggregate.call_args[0][0]
    no_answer_match = next(
        (s for s in pipeline if s.get("$match", {}).get("no_answer") is True),
        None,
    )
    assert no_answer_match is not None


@pytest.mark.unit
async def test_conversation_detail_returns_none_when_missing():
    coll = MagicMock()
    coll.find_one = AsyncMock(return_value=None)
    service = AnalyticsService(coll)

    detail = await service.conversation_detail("tenant-1", "missing-id")

    assert detail is None
    coll.find_one.assert_awaited_once()
    call = coll.find_one.await_args[0][0]
    assert call == {"_id": "missing-id", "tenant_id": "tenant-1"}


@pytest.mark.unit
async def test_conversation_detail_passes_through_messages():
    now = datetime.now(timezone.utc)
    coll = MagicMock()
    coll.find_one = AsyncMock(
        return_value={
            "_id": "conv-1",
            "tenant_id": "tenant-1",
            "session_id": "sess-1",
            "created_at": now,
            "updated_at": now,
            "messages": [
                {"role": "user", "content": "hi", "timestamp": now, "sources": []},
                {
                    "role": "assistant",
                    "content": "hello",
                    "timestamp": now,
                    "sources": ["doc-a"],
                },
            ],
        }
    )
    service = AnalyticsService(coll)

    detail = await service.conversation_detail("tenant-1", "conv-1")

    assert detail is not None
    assert detail.conversation_id == "conv-1"
    assert len(detail.messages) == 2
    assert detail.messages[1].sources == ["doc-a"]
