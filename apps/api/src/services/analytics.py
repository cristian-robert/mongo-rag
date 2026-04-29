"""Conversation analytics service.

All aggregations are tenant-scoped. Pipelines target the `conversations`
collection, which stores chat history per CLAUDE.md schema. We treat each
embedded message as the unit of analysis via $unwind.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from pymongo.asynchronous.collection import AsyncCollection

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

logger = logging.getLogger(__name__)

# Hard caps applied to any caller-supplied window — also defended in the
# Pydantic request validator. This is a defense-in-depth check that prevents
# a malicious or buggy request from running an unbounded aggregation.
MIN_WINDOW_DAYS = 1
MAX_WINDOW_DAYS = 365
DEFAULT_WINDOW_DAYS = 30

MIN_PAGE_SIZE = 1
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 25

# Truncations applied before any string is sent to the dashboard.
QUERY_DISPLAY_MAX = 500
ANSWER_PREVIEW_MAX = 200
TOP_QUERY_KEY_MAX = 200
TOP_QUERIES_LIMIT = 10


def _resolve_window(days: int | None) -> tuple[int, datetime, datetime]:
    """Validate the requested window and return (days, start, end)."""
    window = days if days is not None else DEFAULT_WINDOW_DAYS
    if window < MIN_WINDOW_DAYS:
        window = MIN_WINDOW_DAYS
    if window > MAX_WINDOW_DAYS:
        window = MAX_WINDOW_DAYS
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=window)
    return window, start, end


class AnalyticsService:
    """Tenant-scoped aggregations over the conversations collection."""

    def __init__(self, conversations: AsyncCollection) -> None:
        self.conversations = conversations

    async def overview(
        self,
        tenant_id: str,
        window_days: int | None = None,
        bot_id: str | None = None,
    ) -> AnalyticsOverview:
        """Compute total counts, no-answer rate, and top queries."""
        window, start, end = _resolve_window(window_days)
        match: dict[str, Any] = {"tenant_id": tenant_id, "updated_at": {"$gte": start, "$lte": end}}
        if bot_id:
            match["metadata.bot_id"] = bot_id

        # Single pipeline using $facet so we make one round-trip.
        pipeline: list[dict[str, Any]] = [
            {"$match": match},
            {
                "$facet": {
                    "totals": [
                        {
                            "$group": {
                                "_id": None,
                                "conversations": {"$sum": 1},
                                "sessions": {"$addToSet": "$session_id"},
                            }
                        }
                    ],
                    "messages": [
                        {"$unwind": "$messages"},
                        {"$match": {"messages.timestamp": {"$gte": start, "$lte": end}}},
                        {
                            "$group": {
                                "_id": "$messages.role",
                                "count": {"$sum": 1},
                                "avg_chars": {
                                    "$avg": {"$strLenCP": {"$ifNull": ["$messages.content", ""]}}
                                },
                                "no_answer": {
                                    "$sum": {
                                        "$cond": [
                                            {
                                                "$and": [
                                                    {"$eq": ["$messages.role", "assistant"]},
                                                    {
                                                        "$eq": [
                                                            {
                                                                "$size": {
                                                                    "$ifNull": [
                                                                        "$messages.sources",
                                                                        [],
                                                                    ]
                                                                }
                                                            },
                                                            0,
                                                        ]
                                                    },
                                                ]
                                            },
                                            1,
                                            0,
                                        ]
                                    }
                                },
                            }
                        },
                    ],
                    "top_queries": [
                        {"$unwind": "$messages"},
                        {
                            "$match": {
                                "messages.role": "user",
                                "messages.timestamp": {"$gte": start, "$lte": end},
                            }
                        },
                        {
                            "$project": {
                                "key": {
                                    "$toLower": {
                                        "$substrCP": [
                                            {"$ifNull": ["$messages.content", ""]},
                                            0,
                                            TOP_QUERY_KEY_MAX,
                                        ]
                                    }
                                }
                            }
                        },
                        {"$group": {"_id": "$key", "count": {"$sum": 1}}},
                        {"$sort": {"count": -1, "_id": 1}},
                        {"$limit": TOP_QUERIES_LIMIT},
                    ],
                }
            },
        ]

        cursor = await self.conversations.aggregate(pipeline)
        docs = await cursor.to_list(length=1)
        facet = docs[0] if docs else {"totals": [], "messages": [], "top_queries": []}

        totals_doc = facet["totals"][0] if facet["totals"] else {}
        total_conversations = int(totals_doc.get("conversations", 0))
        unique_sessions = len(totals_doc.get("sessions", []) or [])

        user_count = 0
        assistant_count = 0
        no_answer_count = 0
        avg_assistant_chars = 0.0
        for entry in facet["messages"]:
            role = entry.get("_id")
            count = int(entry.get("count", 0))
            if role == "user":
                user_count = count
            elif role == "assistant":
                assistant_count = count
                avg_assistant_chars = float(entry.get("avg_chars") or 0.0)
                no_answer_count = int(entry.get("no_answer", 0))

        total_messages = user_count + assistant_count
        no_answer_rate = (no_answer_count / assistant_count) if assistant_count else 0.0

        top: list[TopQuery] = [
            TopQuery(
                query=(entry.get("_id") or "")[:QUERY_DISPLAY_MAX],
                count=int(entry.get("count", 0)),
            )
            for entry in facet["top_queries"]
            if entry.get("_id")
        ]

        return AnalyticsOverview(
            window_days=window,
            period_start=start,
            period_end=end,
            total_conversations=total_conversations,
            total_messages=total_messages,
            total_user_queries=user_count,
            total_assistant_responses=assistant_count,
            unique_sessions=unique_sessions,
            avg_response_chars=round(avg_assistant_chars, 2),
            no_answer_count=no_answer_count,
            no_answer_rate=round(no_answer_rate, 4),
            top_queries=top,
        )

    async def timeseries(
        self,
        tenant_id: str,
        window_days: int | None = None,
        bot_id: str | None = None,
    ) -> AnalyticsTimeseries:
        """Daily counts of user queries and assistant responses."""
        window, start, end = _resolve_window(window_days)
        match: dict[str, Any] = {"tenant_id": tenant_id, "updated_at": {"$gte": start, "$lte": end}}
        if bot_id:
            match["metadata.bot_id"] = bot_id

        pipeline: list[dict[str, Any]] = [
            {"$match": match},
            {"$unwind": "$messages"},
            {"$match": {"messages.timestamp": {"$gte": start, "$lte": end}}},
            {
                "$group": {
                    "_id": {
                        "date": {
                            "$dateToString": {
                                "format": "%Y-%m-%d",
                                "date": "$messages.timestamp",
                                "timezone": "UTC",
                            }
                        },
                        "role": "$messages.role",
                    },
                    "count": {"$sum": 1},
                }
            },
        ]
        cursor = await self.conversations.aggregate(pipeline)
        rows = await cursor.to_list(length=window * 4 + 32)

        buckets: dict[str, dict[str, int]] = {}
        for row in rows:
            key = row["_id"]
            date_key = key.get("date")
            role = key.get("role")
            if not date_key:
                continue
            bucket = buckets.setdefault(date_key, {"user": 0, "assistant": 0})
            if role == "user":
                bucket["user"] += int(row.get("count", 0))
            elif role == "assistant":
                bucket["assistant"] += int(row.get("count", 0))

        # Densify the series so every day in the window has a point.
        points: list[TimeseriesPoint] = []
        cursor_day = start.replace(hour=0, minute=0, second=0, microsecond=0)
        end_day = end.replace(hour=0, minute=0, second=0, microsecond=0)
        while cursor_day <= end_day:
            date_key = cursor_day.strftime("%Y-%m-%d")
            bucket = buckets.get(date_key, {"user": 0, "assistant": 0})
            points.append(
                TimeseriesPoint(
                    date=date_key,
                    user_queries=bucket["user"],
                    assistant_responses=bucket["assistant"],
                )
            )
            cursor_day += timedelta(days=1)

        return AnalyticsTimeseries(
            window_days=window,
            period_start=start,
            period_end=end,
            points=points,
        )

    async def queries(
        self,
        tenant_id: str,
        window_days: int | None = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        no_answer_only: bool = False,
        bot_id: str | None = None,
    ) -> QueriesPage:
        """Paginated user queries within the window."""
        window, start, end = _resolve_window(window_days)
        if page < 1:
            page = 1
        page_size = max(MIN_PAGE_SIZE, min(MAX_PAGE_SIZE, page_size))
        skip = (page - 1) * page_size

        match: dict[str, Any] = {"tenant_id": tenant_id, "updated_at": {"$gte": start, "$lte": end}}
        if bot_id:
            match["metadata.bot_id"] = bot_id

        message_match: dict[str, Any] = {
            "messages.role": "user",
            "messages.timestamp": {"$gte": start, "$lte": end},
        }

        # We need to pair each user message with the assistant reply that
        # immediately follows it. We do that by zipping messages with their
        # index, then for each user message looking up element idx+1.
        pipeline: list[dict[str, Any]] = [
            {"$match": match},
            {
                "$project": {
                    "session_id": 1,
                    "messages": 1,
                }
            },
            {
                "$addFields": {
                    "indexed": {
                        "$map": {
                            "input": {"$range": [0, {"$size": "$messages"}]},
                            "as": "i",
                            "in": {
                                "i": "$$i",
                                "msg": {"$arrayElemAt": ["$messages", "$$i"]},
                                "next": {
                                    "$arrayElemAt": [
                                        "$messages",
                                        {"$add": ["$$i", 1]},
                                    ]
                                },
                            },
                        }
                    }
                }
            },
            {"$unwind": "$indexed"},
            {
                "$match": {
                    "indexed.msg.role": "user",
                    "indexed.msg.timestamp": {"$gte": start, "$lte": end},
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "conversation_id": {"$toString": "$_id"},
                    "session_id": "$session_id",
                    "query": "$indexed.msg.content",
                    "timestamp": "$indexed.msg.timestamp",
                    "answer_preview": {
                        "$cond": [
                            {"$eq": [{"$ifNull": ["$indexed.next.role", None]}, "assistant"]},
                            {
                                "$substrCP": [
                                    {"$ifNull": ["$indexed.next.content", ""]},
                                    0,
                                    ANSWER_PREVIEW_MAX,
                                ]
                            },
                            None,
                        ]
                    },
                    "sources_count": {
                        "$cond": [
                            {"$eq": [{"$ifNull": ["$indexed.next.role", None]}, "assistant"]},
                            {"$size": {"$ifNull": ["$indexed.next.sources", []]}},
                            0,
                        ]
                    },
                    "no_answer": {
                        "$cond": [
                            {"$eq": [{"$ifNull": ["$indexed.next.role", None]}, "assistant"]},
                            {
                                "$eq": [
                                    {"$size": {"$ifNull": ["$indexed.next.sources", []]}},
                                    0,
                                ]
                            },
                            True,
                        ]
                    },
                }
            },
        ]

        if no_answer_only:
            pipeline.append({"$match": {"no_answer": True}})
            message_match["__no_answer_only"] = True  # marker, not used directly

        pipeline.extend(
            [
                {
                    "$facet": {
                        "items": [
                            {"$sort": {"timestamp": -1}},
                            {"$skip": skip},
                            {"$limit": page_size},
                        ],
                        "total": [{"$count": "n"}],
                    }
                }
            ]
        )

        cursor = await self.conversations.aggregate(pipeline)
        docs = await cursor.to_list(length=1)
        facet = docs[0] if docs else {"items": [], "total": []}

        items_raw = facet.get("items", []) or []
        total = int(facet.get("total", [{}])[0].get("n", 0)) if facet.get("total") else 0

        items: list[QueryRow] = []
        for row in items_raw:
            query_text = (row.get("query") or "")[:QUERY_DISPLAY_MAX]
            preview = row.get("answer_preview")
            if preview is not None:
                preview = preview[:ANSWER_PREVIEW_MAX]
            items.append(
                QueryRow(
                    conversation_id=str(row.get("conversation_id") or ""),
                    session_id=str(row.get("session_id") or ""),
                    query=query_text,
                    answer_preview=preview,
                    sources_count=int(row.get("sources_count", 0)),
                    no_answer=bool(row.get("no_answer", False)),
                    timestamp=row.get("timestamp"),
                )
            )

        return QueriesPage(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            has_more=(skip + len(items)) < total,
        )

    async def conversation_detail(
        self,
        tenant_id: str,
        conversation_id: str,
    ) -> ConversationDetail | None:
        """Return the full transcript for one conversation, tenant-scoped."""
        doc = await self.conversations.find_one({"_id": conversation_id, "tenant_id": tenant_id})
        if not doc:
            return None
        msgs = []
        for m in doc.get("messages", []) or []:
            msgs.append(
                ConversationMessage(
                    role=str(m.get("role", "user")),
                    content=str(m.get("content", "")),
                    sources=list(m.get("sources", []) or []),
                    timestamp=m.get("timestamp") or doc.get("created_at"),
                )
            )
        return ConversationDetail(
            conversation_id=str(doc.get("_id")),
            session_id=str(doc.get("session_id", "")),
            created_at=doc.get("created_at"),
            updated_at=doc.get("updated_at"),
            messages=msgs,
        )
