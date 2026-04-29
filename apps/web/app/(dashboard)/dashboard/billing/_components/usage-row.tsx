import { cn } from "@/lib/utils";

const numberFmt = new Intl.NumberFormat("en-US");

function formatPercent(percent: number): string {
  return `${Math.min(100, Math.round(percent * 100))}%`;
}

export function UsageRow({
  label,
  used,
  limit,
  warning,
  blocked,
  unit,
}: {
  label: string;
  used: number;
  limit: number;
  warning: boolean;
  blocked: boolean;
  unit?: string;
}) {
  const safeLimit = Math.max(limit, 1);
  const pct = Math.min(100, Math.round((used / safeLimit) * 100));
  const tone = blocked
    ? "bg-destructive"
    : warning
      ? "bg-amber-500"
      : "bg-foreground";

  const status = blocked
    ? "Limit reached"
    : warning
      ? "Approaching limit"
      : null;

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[0.85rem] font-medium text-foreground">
          {label}
        </span>
        <span className="font-mono text-[0.78rem] tabular-nums text-muted-foreground">
          {numberFmt.format(used)}
          <span className="px-1 text-muted-foreground/60">/</span>
          {numberFmt.format(limit)}
          {unit ? <span className="ml-1 text-muted-foreground/70">{unit}</span> : null}
        </span>
      </div>
      <div
        role="progressbar"
        aria-label={`${label} usage`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
      >
        <div
          className={cn("h-full rounded-full transition-[width]", tone)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="flex items-center justify-between text-[0.72rem] text-muted-foreground">
        <span className="tabular-nums">{formatPercent(used / safeLimit)}</span>
        {status ? (
          <span
            className={cn(
              "font-medium",
              blocked ? "text-destructive" : "text-amber-600 dark:text-amber-500",
            )}
          >
            {status}
          </span>
        ) : null}
      </div>
    </div>
  );
}
