"""Tests for the analytics router."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.models.analytics import (
    AnalyticsOverview,
    AnalyticsTimeseries,
    ConversationDetail,
    ConversationMessage,
    QueriesPage,
    QueryRow,
    TimeseriesPoint,
    TopQuery,
)
from tests.conftest import make_auth_header


@pytest.fixture
def analytics_client(mock_deps):
    from src.main import app

    with TestClient(app) as c:
        app.state.deps = mock_deps
        yield c


def _overview(window_days: int = 30) -> AnalyticsOverview:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=window_days)
    return AnalyticsOverview(
        window_days=window_days,
        period_start=start,
        period_end=end,
        total_conversations=10,
        total_messages=42,
        total_user_queries=21,
        total_assistant_responses=21,
        unique_sessions=7,
        avg_response_chars=312.5,
        no_answer_count=2,
        no_answer_rate=0.0952,
        top_queries=[TopQuery(query="how do i export data?", count=5)],
    )


@pytest.mark.unit
def test_overview_returns_aggregated_metrics(analytics_client):
    with patch("src.routers.analytics.AnalyticsService") as cls:
        cls.return_value.overview = AsyncMock(return_value=_overview(30))
        response = analytics_client.get("/api/v1/analytics/overview", headers=make_auth_header())
    assert response.status_code == 200
    body = response.json()
    assert body["window_days"] == 30
    assert body["total_conversations"] == 10
    assert body["no_answer_count"] == 2
    assert body["top_queries"][0]["query"] == "how do i export data?"


@pytest.mark.unit
def test_overview_rejects_api_key(analytics_client):
    response = analytics_client.get(
        "/api/v1/analytics/overview",
        headers={"Authorization": "Bearer mrag_abc1234567890123456"},
    )
    assert response.status_code == 403


@pytest.mark.unit
def test_overview_requires_auth(analytics_client):
    response = analytics_client.get("/api/v1/analytics/overview")
    assert response.status_code == 401


@pytest.mark.unit
def test_overview_clamps_window_via_validator(analytics_client):
    response = analytics_client.get(
        "/api/v1/analytics/overview?days=10000", headers=make_auth_header()
    )
    assert response.status_code == 422

    response = analytics_client.get("/api/v1/analytics/overview?days=0", headers=make_auth_header())
    assert response.status_code == 422


@pytest.mark.unit
def test_timeseries_returns_points(analytics_client):
    end = datetime.now(timezone.utc)
    payload = AnalyticsTimeseries(
        window_days=7,
        period_start=end - timedelta(days=7),
        period_end=end,
        points=[TimeseriesPoint(date="2026-04-22", user_queries=2, assistant_responses=2)],
    )
    with patch("src.routers.analytics.AnalyticsService") as cls:
        cls.return_value.timeseries = AsyncMock(return_value=payload)
        response = analytics_client.get(
            "/api/v1/analytics/timeseries?days=7", headers=make_auth_header()
        )
    assert response.status_code == 200
    assert response.json()["points"][0]["user_queries"] == 2


@pytest.mark.unit
def test_queries_endpoint_returns_paginated(analytics_client):
    payload = QueriesPage(
        items=[
            QueryRow(
                conversation_id="c1",
                session_id="s1",
                query="What is RAG?",
                answer_preview="Retrieval augmented generation",
                sources_count=2,
                no_answer=False,
                timestamp=datetime.now(timezone.utc),
            )
        ],
        page=1,
        page_size=25,
        total=1,
        has_more=False,
    )
    with patch("src.routers.analytics.AnalyticsService") as cls:
        cls.return_value.queries = AsyncMock(return_value=payload)
        response = analytics_client.get(
            "/api/v1/analytics/queries?page=1&page_size=25&no_answer_only=false",
            headers=make_auth_header(),
        )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["query"] == "What is RAG?"


@pytest.mark.unit
def test_queries_invalid_page_size_rejected(analytics_client):
    response = analytics_client.get(
        "/api/v1/analytics/queries?page_size=999", headers=make_auth_header()
    )
    assert response.status_code == 422


@pytest.mark.unit
def test_conversation_detail_404_when_missing(analytics_client):
    with patch("src.routers.analytics.AnalyticsService") as cls:
        cls.return_value.conversation_detail = AsyncMock(return_value=None)
        response = analytics_client.get(
            "/api/v1/analytics/conversations/missing-id", headers=make_auth_header()
        )
    assert response.status_code == 404


@pytest.mark.unit
def test_conversation_detail_returns_messages(analytics_client):
    now = datetime.now(timezone.utc)
    payload = ConversationDetail(
        conversation_id="c1",
        session_id="s1",
        created_at=now,
        updated_at=now,
        messages=[
            ConversationMessage(role="user", content="hi", sources=[], timestamp=now),
            ConversationMessage(
                role="assistant", content="hello!", sources=["doc-a"], timestamp=now
            ),
        ],
    )
    with patch("src.routers.analytics.AnalyticsService") as cls:
        cls.return_value.conversation_detail = AsyncMock(return_value=payload)
        response = analytics_client.get(
            "/api/v1/analytics/conversations/c1", headers=make_auth_header()
        )
    assert response.status_code == 200
    body = response.json()
    assert body["messages"][1]["role"] == "assistant"
    assert body["messages"][1]["sources"] == ["doc-a"]


@pytest.mark.unit
def test_conversation_detail_rejects_oversized_id(analytics_client):
    big_id = "x" * 200
    response = analytics_client.get(
        f"/api/v1/analytics/conversations/{big_id}", headers=make_auth_header()
    )
    assert response.status_code == 404
