"""Analytics response models for the dashboard."""

from datetime import datetime

from pydantic import BaseModel, Field


class TopQuery(BaseModel):
    """A frequently-asked user query with occurrence count."""

    query: str = Field(..., description="The user's message text (truncated to 200 chars)")
    count: int = Field(..., ge=0, description="How many times this query was asked")


class AnalyticsOverview(BaseModel):
    """Aggregated analytics for the requested window."""

    window_days: int = Field(..., ge=1, le=365)
    period_start: datetime
    period_end: datetime
    total_conversations: int = Field(..., ge=0)
    total_messages: int = Field(..., ge=0)
    total_user_queries: int = Field(..., ge=0)
    total_assistant_responses: int = Field(..., ge=0)
    unique_sessions: int = Field(..., ge=0)
    avg_response_chars: float = Field(..., ge=0.0, description="Average assistant reply length")
    no_answer_count: int = Field(
        ...,
        ge=0,
        description="Assistant responses with empty sources (likely 'I don't know')",
    )
    no_answer_rate: float = Field(..., ge=0.0, le=1.0)
    top_queries: list[TopQuery] = Field(default_factory=list)


class TimeseriesPoint(BaseModel):
    """A single bucket on the volume timeseries."""

    date: str = Field(..., description="ISO date YYYY-MM-DD (UTC bucket)")
    user_queries: int = Field(..., ge=0)
    assistant_responses: int = Field(..., ge=0)


class AnalyticsTimeseries(BaseModel):
    """Daily query/response volume across the window."""

    window_days: int = Field(..., ge=1, le=365)
    period_start: datetime
    period_end: datetime
    points: list[TimeseriesPoint] = Field(default_factory=list)


class QueryRow(BaseModel):
    """A single user query row, used in the queries table."""

    conversation_id: str
    session_id: str
    query: str = Field(..., description="The user's message text")
    answer_preview: str | None = Field(
        default=None, description="First 200 chars of the assistant reply, if any"
    )
    sources_count: int = Field(..., ge=0)
    no_answer: bool = Field(..., description="True when the assistant answered with no sources")
    timestamp: datetime


class QueriesPage(BaseModel):
    """Paginated query results."""

    items: list[QueryRow]
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)
    total: int = Field(..., ge=0)
    has_more: bool


class ConversationMessage(BaseModel):
    """A single message inside a conversation, redacted for display."""

    role: str
    content: str
    sources: list[str] = Field(default_factory=list)
    timestamp: datetime


class ConversationDetail(BaseModel):
    """Full conversation transcript for the drawer view."""

    conversation_id: str
    session_id: str
    created_at: datetime
    updated_at: datetime
    messages: list[ConversationMessage]
