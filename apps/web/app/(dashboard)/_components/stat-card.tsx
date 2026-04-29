import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function StatCard({
  label,
  value,
  hint,
  icon,
  className,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "group/stat relative flex flex-col gap-2 overflow-hidden rounded-xl border border-border bg-card p-4 text-card-foreground",
        "before:absolute before:inset-x-4 before:top-0 before:h-px before:bg-gradient-to-r before:from-transparent before:via-foreground/15 before:to-transparent",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[0.72rem] font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </span>
        {icon ? (
          <span
            aria-hidden="true"
            className="grid size-7 place-items-center rounded-md bg-muted text-foreground/70"
          >
            {icon}
          </span>
        ) : null}
      </div>
      <div className="font-heading text-2xl font-semibold tracking-tight text-foreground tabular-nums">
        {value}
      </div>
      {hint ? (
        <div className="text-[0.78rem] text-muted-foreground">{hint}</div>
      ) : null}
    </div>
  );
}
