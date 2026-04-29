import Link from "next/link";

import { cn } from "@/lib/utils";

const WINDOWS = [
  { value: 7, label: "7d" },
  { value: 14, label: "14d" },
  { value: 30, label: "30d" },
  { value: 90, label: "90d" },
  { value: 180, label: "6m" },
  { value: 365, label: "1y" },
] as const;

export function FilterBar({
  days,
  noAnswerOnly,
}: {
  days: number;
  noAnswerOnly: boolean;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card/60 px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[0.72rem] font-medium uppercase tracking-wide text-muted-foreground">
          Window
        </span>
        <nav aria-label="Time window" className="flex items-center gap-1">
          {WINDOWS.map((opt) => {
            const active = opt.value === days;
            const href = `/dashboard/analytics?days=${opt.value}${noAnswerOnly ? "&no_answer=1" : ""}`;
            return (
              <Link
                key={opt.value}
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "rounded-md border px-2.5 py-1 text-[0.78rem] font-medium tabular-nums transition-colors",
                  active
                    ? "border-foreground/30 bg-foreground text-background"
                    : "border-border text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                {opt.label}
              </Link>
            );
          })}
        </nav>
      </div>

      <div className="flex items-center gap-2">
        <Link
          href={`/dashboard/analytics?days=${days}${noAnswerOnly ? "" : "&no_answer=1"}`}
          aria-pressed={noAnswerOnly}
          className={cn(
            "rounded-md border px-2.5 py-1 text-[0.78rem] font-medium transition-colors",
            noAnswerOnly
              ? "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400"
              : "border-border text-muted-foreground hover:bg-muted hover:text-foreground",
          )}
        >
          {noAnswerOnly ? "Showing unanswered only" : "Show unanswered only"}
        </Link>
      </div>
    </div>
  );
}
