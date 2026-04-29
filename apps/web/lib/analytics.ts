import "server-only";

import { apiFetch } from "@/lib/api-client";

export interface TopQuery {
  query: string;
  count: number;
}

export interface AnalyticsOverview {
  window_days: number;
  period_start: string;
  period_end: string;
  total_conversations: number;
  total_messages: number;
  total_user_queries: number;
  total_assistant_responses: number;
  unique_sessions: number;
  avg_response_chars: number;
  no_answer_count: number;
  no_answer_rate: number;
  top_queries: TopQuery[];
}

export interface TimeseriesPoint {
  date: string;
  user_queries: number;
  assistant_responses: number;
}

export interface AnalyticsTimeseries {
  window_days: number;
  period_start: string;
  period_end: string;
  points: TimeseriesPoint[];
}

export interface QueryRow {
  conversation_id: string;
  session_id: string;
  query: string;
  answer_preview: string | null;
  sources_count: number;
  no_answer: boolean;
  timestamp: string;
}

export interface QueriesPage {
  items: QueryRow[];
  page: number;
  page_size: number;
  total: number;
  has_more: boolean;
}

export interface ConversationMessage {
  role: string;
  content: string;
  sources: string[];
  timestamp: string;
}

export interface ConversationDetail {
  conversation_id: string;
  session_id: string;
  created_at: string;
  updated_at: string;
  messages: ConversationMessage[];
}

const ALLOWED_DAYS = [7, 14, 30, 90, 180, 365] as const;
export type WindowDays = (typeof ALLOWED_DAYS)[number];

export function isValidWindow(value: number): value is WindowDays {
  return (ALLOWED_DAYS as readonly number[]).includes(value);
}

export async function fetchOverview(days: WindowDays): Promise<AnalyticsOverview> {
  return apiFetch<AnalyticsOverview>(`/api/v1/analytics/overview?days=${days}`);
}

export async function fetchTimeseries(days: WindowDays): Promise<AnalyticsTimeseries> {
  return apiFetch<AnalyticsTimeseries>(`/api/v1/analytics/timeseries?days=${days}`);
}

export async function fetchQueries(params: {
  days: WindowDays;
  page?: number;
  pageSize?: number;
  noAnswerOnly?: boolean;
}): Promise<QueriesPage> {
  const search = new URLSearchParams({
    days: String(params.days),
    page: String(params.page ?? 1),
    page_size: String(params.pageSize ?? 25),
    no_answer_only: String(params.noAnswerOnly ?? false),
  });
  return apiFetch<QueriesPage>(`/api/v1/analytics/queries?${search.toString()}`);
}

export async function fetchConversation(id: string): Promise<ConversationDetail> {
  // The id is opaque (UUID v4). Encode for safety; backend additionally
  // bounds length and 404s on cross-tenant lookups.
  return apiFetch<ConversationDetail>(
    `/api/v1/analytics/conversations/${encodeURIComponent(id)}`,
  );
}
