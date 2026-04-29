import { Bot, FileText, KeyRound, MessageSquareText, Upload, Zap } from "lucide-react";

import { auth } from "@/lib/auth";

import { QuickAction } from "../_components/quick-action";
import { StatCard } from "../_components/stat-card";
import { UsageMeter } from "../_components/usage-meter";

type OverviewMetrics = {
  plan: "free" | "starter" | "pro" | "enterprise";
  queriesUsed: number;
  queriesLimit: number;
  documentCount: number;
  activeBotCount: number;
};

const PLAN_LABELS: Record<OverviewMetrics["plan"], string> = {
  free: "Free",
  starter: "Starter",
  pro: "Pro",
  enterprise: "Enterprise",
};

async function loadOverview(tenantId: string): Promise<OverviewMetrics> {
  // Placeholder data keyed by tenant — wired to Supabase + Mongo aggregation
  // in a follow-up (subscriptions, documents, bots).
  void tenantId;
  return {
    plan: "free",
    queriesUsed: 0,
    queriesLimit: 1000,
    documentCount: 0,
    activeBotCount: 0,
  };
}

function formatNumber(n: number): string {
  return new Intl.NumberFormat("en-US").format(n);
}

export default async function DashboardOverviewPage() {
  const session = await auth();
  const email = session?.user?.email ?? "there";
  const tenantId = session?.user?.tenant_id ?? "";

  const metrics = await loadOverview(tenantId);
  const usagePct = Math.round(
    (metrics.queriesUsed / Math.max(metrics.queriesLimit, 1)) * 100,
  );

  return (
    <div className="flex flex-col gap-7">
      <header className="flex flex-col gap-1">
        <p className="text-[0.78rem] font-medium uppercase tracking-wide text-muted-foreground">
          Overview
        </p>
        <h1 className="font-heading text-2xl font-semibold tracking-tight text-foreground sm:text-[1.65rem]">
          Welcome back, {email}
        </h1>
        <p className="text-sm text-muted-foreground">
          A snapshot of your workspace usage and content.
        </p>
      </header>

      <section aria-labelledby="metrics-heading" className="flex flex-col gap-3">
        <h2 id="metrics-heading" className="sr-only">
          Key metrics
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Plan"
            value={PLAN_LABELS[metrics.plan]}
            hint={`${formatNumber(metrics.queriesLimit)} queries / month`}
            icon={<Zap className="size-4" />}
          />
          <StatCard
            label="Queries used"
            value={
              <span>
                {formatNumber(metrics.queriesUsed)}
                <span className="ml-1 text-base font-medium text-muted-foreground">
                  / {formatNumber(metrics.queriesLimit)}
                </span>
              </span>
            }
            hint={
              <div className="flex flex-col gap-1.5 pt-1">
                <UsageMeter
                  used={metrics.queriesUsed}
                  limit={metrics.queriesLimit}
                />
                <span>{usagePct}% of monthly limit</span>
              </div>
            }
            icon={<MessageSquareText className="size-4" />}
          />
          <StatCard
            label="Documents"
            value={formatNumber(metrics.documentCount)}
            hint="Indexed sources"
            icon={<FileText className="size-4" />}
          />
          <StatCard
            label="Active bots"
            value={formatNumber(metrics.activeBotCount)}
            hint="Deployed assistants"
            icon={<Bot className="size-4" />}
          />
        </div>
      </section>

      <section aria-labelledby="actions-heading" className="flex flex-col gap-3">
        <div className="flex items-end justify-between gap-3">
          <h2
            id="actions-heading"
            className="font-heading text-base font-medium tracking-tight text-foreground"
          >
            Quick actions
          </h2>
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          <QuickAction
            href="/dashboard/documents"
            label="Upload document"
            description="Ingest a PDF, Word or web page into your knowledge base."
            icon={<Upload className="size-4" aria-hidden="true" />}
          />
          <QuickAction
            href="/dashboard/bots"
            label="Create a bot"
            description="Configure a new assistant with custom prompts and tools."
            icon={<Bot className="size-4" aria-hidden="true" />}
          />
          <QuickAction
            href="/dashboard/api-keys"
            label="Get script tag"
            description="Generate keys and copy the snippet to embed your widget."
            icon={<KeyRound className="size-4" aria-hidden="true" />}
          />
        </div>
      </section>
    </div>
  );
}
