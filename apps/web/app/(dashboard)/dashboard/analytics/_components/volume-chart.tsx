import type { TimeseriesPoint } from "@/lib/analytics";

const VIEW_W = 720;
const VIEW_H = 220;
const PAD_L = 36;
const PAD_R = 12;
const PAD_T = 16;
const PAD_B = 28;

function buildPath(values: number[], maxY: number): string {
  if (values.length === 0) return "";
  const innerW = VIEW_W - PAD_L - PAD_R;
  const innerH = VIEW_H - PAD_T - PAD_B;
  const stepX = values.length > 1 ? innerW / (values.length - 1) : 0;
  const scaleY = maxY > 0 ? innerH / maxY : 0;
  return values
    .map((v, i) => {
      const x = PAD_L + i * stepX;
      const y = VIEW_H - PAD_B - v * scaleY;
      return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
}

function buildArea(values: number[], maxY: number): string {
  if (values.length === 0) return "";
  const innerW = VIEW_W - PAD_L - PAD_R;
  const innerH = VIEW_H - PAD_T - PAD_B;
  const stepX = values.length > 1 ? innerW / (values.length - 1) : 0;
  const scaleY = maxY > 0 ? innerH / maxY : 0;
  const lastX = PAD_L + (values.length - 1) * stepX;
  const baseY = VIEW_H - PAD_B;
  const segments = values
    .map((v, i) => {
      const x = PAD_L + i * stepX;
      const y = VIEW_H - PAD_B - v * scaleY;
      return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
  return `${segments} L ${lastX.toFixed(1)} ${baseY} L ${PAD_L} ${baseY} Z`;
}

function pickAxisTicks(maxY: number): number[] {
  if (maxY <= 0) return [0, 1];
  const steps = 4;
  const raw = maxY / steps;
  const magnitude = Math.pow(10, Math.floor(Math.log10(raw)));
  const niceStep = Math.max(1, Math.ceil(raw / magnitude) * magnitude);
  const top = Math.ceil(maxY / niceStep) * niceStep;
  const out: number[] = [];
  for (let v = 0; v <= top; v += niceStep) out.push(v);
  return out;
}

function formatDateLabel(iso: string): string {
  // iso is YYYY-MM-DD — render as MMM D in en-US.
  const d = new Date(`${iso}T00:00:00Z`);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

export function VolumeChart({ points }: { points: TimeseriesPoint[] }) {
  const userValues = points.map((p) => p.user_queries);
  const totalQueries = userValues.reduce((acc, v) => acc + v, 0);
  const peakDate = points.reduce<TimeseriesPoint | null>((best, p) => {
    if (!best || p.user_queries > best.user_queries) return p;
    return best;
  }, null);
  const maxY = Math.max(1, ...userValues);
  const ticks = pickAxisTicks(maxY);
  const tickMax = Math.max(maxY, ticks[ticks.length - 1] ?? maxY);

  const linePath = buildPath(userValues, tickMax);
  const areaPath = buildArea(userValues, tickMax);

  const labelStride =
    points.length <= 8 ? 1 : Math.max(1, Math.floor(points.length / 6));

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-baseline justify-between gap-3">
        <div>
          <p className="text-[0.72rem] font-medium uppercase tracking-wide text-muted-foreground">
            Query volume
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {totalQueries.toLocaleString("en-US")} user queries across the window
            {peakDate ? `, peaking on ${formatDateLabel(peakDate.date)}` : ""}.
          </p>
        </div>
      </div>

      <svg
        role="img"
        aria-label="Daily user query volume timeseries"
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        className="mt-4 h-[220px] w-full"
        preserveAspectRatio="none"
      >
        <title>Daily user query volume</title>

        {ticks.map((t, i) => {
          const innerH = VIEW_H - PAD_T - PAD_B;
          const scaleY = tickMax > 0 ? innerH / tickMax : 0;
          const y = VIEW_H - PAD_B - t * scaleY;
          return (
            <g key={`tick-${i}`}>
              <line
                x1={PAD_L}
                x2={VIEW_W - PAD_R}
                y1={y}
                y2={y}
                stroke="currentColor"
                strokeOpacity={i === 0 ? 0.25 : 0.1}
                strokeDasharray={i === 0 ? undefined : "2 4"}
              />
              <text
                x={PAD_L - 6}
                y={y + 3}
                textAnchor="end"
                fontSize="10"
                fill="currentColor"
                fillOpacity="0.55"
              >
                {t.toLocaleString("en-US")}
              </text>
            </g>
          );
        })}

        {areaPath ? (
          <path d={areaPath} fill="currentColor" fillOpacity="0.08" />
        ) : null}
        {linePath ? (
          <path
            d={linePath}
            fill="none"
            stroke="currentColor"
            strokeOpacity="0.85"
            strokeWidth="1.5"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        ) : null}

        {points.map((p, i) => {
          if (i % labelStride !== 0 && i !== points.length - 1) return null;
          const innerW = VIEW_W - PAD_L - PAD_R;
          const stepX = points.length > 1 ? innerW / (points.length - 1) : 0;
          const x = PAD_L + i * stepX;
          return (
            <text
              key={`x-${p.date}`}
              x={x}
              y={VIEW_H - 8}
              textAnchor="middle"
              fontSize="10"
              fill="currentColor"
              fillOpacity="0.55"
            >
              {formatDateLabel(p.date)}
            </text>
          );
        })}
      </svg>

      <p className="sr-only">
        Daily query counts:
        {points
          .map((p) => ` ${formatDateLabel(p.date)}: ${p.user_queries}`)
          .join(",")}
        .
      </p>
    </div>
  );
}
