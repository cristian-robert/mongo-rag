import { cn } from "@/lib/utils";

export function UsageMeter({
  used,
  limit,
}: {
  used: number;
  limit: number;
}) {
  const safeLimit = Math.max(limit, 1);
  const pct = Math.min(100, Math.round((used / safeLimit) * 100));
  const tone =
    pct >= 90
      ? "bg-destructive"
      : pct >= 75
        ? "bg-amber-500"
        : "bg-foreground";

  return (
    <div
      role="progressbar"
      aria-label="Query usage"
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
  );
}
