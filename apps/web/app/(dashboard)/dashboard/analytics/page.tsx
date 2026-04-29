import type { Metadata } from "next";
import { Suspense } from "react";
import { MessageSquare, Sparkles, TimerReset, Users } from "lucide-react";

import { ApiError } from "@/lib/api-client";
import {
  fetchConversation,
  fetchOverview,
  fetchQueries,
  fetchTimeseries,
  isValidWindow,
  type WindowDays,
} from "@/lib/analytics";

import { StatCard } from "../../_components/stat-card";
import { ConversationDialog } from "./_components/conversation-dialog";
import { FilterBar } from "./_components/filter-bar";
import { QueriesTable } from "./_components/queries-table";
import { VolumeChart } from "./_components/volume-chart";

export const metadata: Metadata = {
  title: "Analytics — MongoRAG",
  description:
    "Conversation analytics, query insights, and unanswered-question detection.",
};

// Per-request JWT minted server-side; analytics data must always reflect
// the latest tenant-scoped state. No prerender.
export const dynamic = "force-dynamic";

const DEFAULT_WINDOW: WindowDays = 30;
const PAGE_SIZE = 25;

type SearchParams = {
  days?: string;
  page?: string;
  no_answer?: string;
  conversation?: string;
};

function parseWindow(raw: string | undefined): WindowDays {
  if (!raw) return DEFAULT_WINDOW;
  const n = Number.parseInt(raw, 10);
  if (Number.isFinite(n) && isValidWindow(n)) return n;
  return DEFAULT_WINDOW;
}

function parsePage(raw: string | undefined): number {
  if (!raw) return 1;
  const n = Number.parseInt(raw, 10);
  if (!Number.isFinite(n) || n < 1) return 1;
  return Math.min(n, 1000);
}

function formatNumber(n: number): string {
  return new Intl.NumberFormat("en-US").format(n);
}

function formatPercent(rate: number): string {
  return `${(rate * 100).toFixed(1)}%`;
}

async function ConversationLoader({
  conversationId,
  closeHref,
}: {
  conversationId: string;
  closeHref: string;
}) {
  // 404 (cross-tenant or missing) becomes silent — closing the modal
  // is enough; the user is back on the dashboard. Do not leak details.
  let detail: Awaited<ReturnType<typeof fetchConversation>> | null = null;
  try {
    detail = await fetchConversation(conversationId);
  } catch (err) {
    void err;
    detail = null;
  }
  if (!detail) return null;
  return <ConversationDialog detail={detail} closeHref={closeHref} />;
}

export default async function AnalyticsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const sp = await searchParams;
  const days = parseWindow(sp.days);
  const page = parsePage(sp.page);
  const noAnswerOnly = sp.no_answer === "1";
  const conversationId = sp.conversation ?? null;

  let initialError: string | null = null;
  let overview: Awaited<ReturnType<typeof fetchOverview>> | null = null;
  let timeseries: Awaited<ReturnType<typeof fetchTimeseries>> | null = null;
  let queries: Awaited<ReturnType<typeof fetchQueries>> | null = null;

  try {
    const [overviewRes, tsRes, queriesRes] = await Promise.all([
      fetchOverview(days),
      fetchTimeseries(days),
      fetchQueries({ days, page, pageSize: PAGE_SIZE, noAnswerOnly }),
    ]);
    overview = overviewRes;
    timeseries = tsRes;
    queries = queriesRes;
  } catch (err) {
    initialError =
      err instanceof ApiError
        ? err.message
        : "Could not reach the API. Try again in a moment.";
  }

  const closeHref = `/dashboard/analytics?days=${days}&page=${page}${noAnswerOnly ? "&no_answer=1" : ""}`;

  return (
    <div className="mx-auto w-full max-w-6xl space-y-7 px-6 py-10">
      <header className="flex flex-col gap-2">
        <p className="font-mono text-[0.7rem] tracking-[0.2em] text-muted-foreground uppercase">
          Insights
        </p>
        <h1 className="font-heading text-2xl leading-tight font-medium tracking-tight">
          Analytics
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          See how your bot is being used, which questions come up most, and
          where your knowledge base has gaps. All metrics are tenant-scoped and
          recompute on every load.
        </p>
      </header>

      <FilterBar days={days} noAnswerOnly={noAnswerOnly} />

      {initialError ? (
        <div
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive"
        >
          {initialError}
        </div>
      ) : null}

      {overview ? (
        <section
          aria-label="Overview metrics"
          className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
        >
          <StatCard
            label="Conversations"
            value={formatNumber(overview.total_conversations)}
            hint={`${formatNumber(overview.unique_sessions)} unique sessions`}
            icon={<MessageSquare className="size-4" aria-hidden="true" />}
          />
          <StatCard
            label="Questions asked"
            value={formatNumber(overview.total_user_queries)}
            hint={`${formatNumber(overview.total_assistant_responses)} replies sent`}
            icon={<Sparkles className="size-4" aria-hidden="true" />}
          />
          <StatCard
            label="Avg reply length"
            value={`${formatNumber(Math.round(overview.avg_response_chars))} chars`}
            hint="Mean assistant message size"
            icon={<TimerReset className="size-4" aria-hidden="true" />}
          />
          <StatCard
            label="Unanswered rate"
            value={formatPercent(overview.no_answer_rate)}
            hint={`${formatNumber(overview.no_answer_count)} replies without sources`}
            icon={<Users className="size-4" aria-hidden="true" />}
          />
        </section>
      ) : null}

      {timeseries ? <VolumeChart points={timeseries.points} /> : null}

      {overview && overview.top_queries.length > 0 ? (
        <section
          aria-label="Top questions"
          className="rounded-xl border border-border bg-card p-5"
        >
          <p className="text-[0.72rem] font-medium uppercase tracking-wide text-muted-foreground">
            Top questions
          </p>
          <ol className="mt-3 flex flex-col divide-y divide-border/60">
            {overview.top_queries.map((q) => (
              <li
                key={q.query}
                className="flex items-center justify-between gap-4 py-2 text-sm"
              >
                <span className="line-clamp-1 max-w-[80%] text-foreground">
                  {q.query}
                </span>
                <span className="tabular-nums text-muted-foreground">
                  ×{q.count}
                </span>
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      {queries ? (
        <section aria-label="All queries" className="space-y-3">
          <h2 className="font-heading text-base font-medium tracking-tight">
            All queries
          </h2>
          <QueriesTable
            page={queries}
            days={days}
            noAnswerOnly={noAnswerOnly}
          />
        </section>
      ) : null}

      {conversationId ? (
        <Suspense fallback={null}>
          <ConversationLoader
            conversationId={conversationId}
            closeHref={closeHref}
          />
        </Suspense>
      ) : null}
    </div>
  );
}
