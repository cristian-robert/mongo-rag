import { CalendarClock, ShieldCheck } from "lucide-react";

import { cn } from "@/lib/utils";
import type { PlanTier, UsageResponse } from "@/lib/billing";

const PLAN_LABELS: Record<PlanTier, string> = {
  free: "Free",
  starter: "Starter",
  pro: "Pro",
  enterprise: "Enterprise",
};

function formatDate(value: string): string {
  try {
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

export function CurrentPlanCard({
  usage,
  loadError,
}: {
  usage: UsageResponse | null;
  loadError: string | null;
}) {
  const plan = usage?.plan ?? "free";
  const label = PLAN_LABELS[plan];
  const renewal = usage ? formatDate(usage.period_end) : null;

  return (
    <section
      aria-labelledby="current-plan-heading"
      className={cn(
        "relative flex flex-col gap-4 overflow-hidden rounded-xl border border-border bg-card p-5 text-card-foreground",
        "before:absolute before:inset-x-5 before:top-0 before:h-px before:bg-gradient-to-r before:from-transparent before:via-foreground/15 before:to-transparent",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <p
            id="current-plan-heading"
            className="font-mono text-[0.7rem] tracking-[0.2em] text-muted-foreground uppercase"
          >
            Current plan
          </p>
          <h2 className="font-heading text-2xl font-semibold tracking-tight text-foreground">
            {label}
          </h2>
        </div>
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[0.72rem] font-medium",
            plan === "free"
              ? "border-border bg-muted text-muted-foreground"
              : "border-foreground/15 bg-foreground/5 text-foreground",
          )}
        >
          <ShieldCheck className="size-3" aria-hidden="true" />
          {plan === "free" ? "No card on file" : "Active"}
        </span>
      </div>

      {loadError ? (
        <p
          role="alert"
          className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-[0.78rem] text-destructive"
        >
          {loadError}
        </p>
      ) : (
        <dl className="grid gap-3 sm:grid-cols-2">
          <div className="flex flex-col gap-0.5">
            <dt className="text-[0.72rem] font-medium uppercase tracking-wide text-muted-foreground">
              Renewal
            </dt>
            <dd className="flex items-center gap-1.5 text-[0.85rem] text-foreground">
              <CalendarClock
                className="size-3.5 text-muted-foreground"
                aria-hidden="true"
              />
              {renewal ? (
                <>
                  {renewal}
                  {plan === "free" ? (
                    <span className="text-muted-foreground">
                      &nbsp;· no charge
                    </span>
                  ) : null}
                </>
              ) : (
                <span className="text-muted-foreground">—</span>
              )}
            </dd>
          </div>
          <div className="flex flex-col gap-0.5">
            <dt className="text-[0.72rem] font-medium uppercase tracking-wide text-muted-foreground">
              Rate limit
            </dt>
            <dd className="text-[0.85rem] text-foreground tabular-nums">
              {usage ? `${usage.rate_limit_per_minute} req / min` : "—"}
            </dd>
          </div>
        </dl>
      )}
    </section>
  );
}
