import Link from "next/link";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { QueriesPage } from "@/lib/analytics";

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function QueriesTable({
  page,
  days,
  noAnswerOnly,
}: {
  page: QueriesPage;
  days: number;
  noAnswerOnly: boolean;
}) {
  if (page.items.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-card/50 p-8 text-center">
        <p className="font-heading text-base text-foreground">No queries yet</p>
        <p className="mt-1 text-sm text-muted-foreground">
          {noAnswerOnly
            ? "No unanswered queries in this window — your knowledge base is covering the questions you have received."
            : "Once your widget gets traffic, the questions users ask will surface here."}
        </p>
      </div>
    );
  }

  const baseHref = (target: number) =>
    `/dashboard/analytics?days=${days}&page=${target}${noAnswerOnly ? "&no_answer=1" : ""}`;
  const prevHref = page.page > 1 ? baseHref(page.page - 1) : null;
  const nextHref = page.has_more ? baseHref(page.page + 1) : null;

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[42%]">Question</TableHead>
            <TableHead className="w-[34%]">Answer preview</TableHead>
            <TableHead className="w-[10%]">Sources</TableHead>
            <TableHead className="w-[14%]">When</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {page.items.map((item) => (
            <TableRow key={`${item.conversation_id}-${item.timestamp}`}>
              <TableCell className="align-top">
                <Link
                  href={`/dashboard/analytics?conversation=${encodeURIComponent(item.conversation_id)}&days=${days}&page=${page.page}${noAnswerOnly ? "&no_answer=1" : ""}`}
                  className="block max-w-[420px] truncate text-foreground underline-offset-4 hover:underline focus-visible:outline-none focus-visible:underline"
                >
                  {item.query || "(empty message)"}
                </Link>
                {item.no_answer ? (
                  <span className="mt-1 inline-flex items-center rounded-md border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 text-[0.66rem] font-medium uppercase tracking-wide text-amber-700 dark:text-amber-400">
                    Unanswered
                  </span>
                ) : null}
              </TableCell>
              <TableCell className="align-top text-muted-foreground">
                <span className="line-clamp-2 max-w-[360px]">
                  {item.answer_preview ?? "—"}
                </span>
              </TableCell>
              <TableCell className="align-top tabular-nums text-foreground/80">
                {item.sources_count}
              </TableCell>
              <TableCell className="align-top text-muted-foreground tabular-nums">
                {formatTimestamp(item.timestamp)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <div className="flex items-center justify-between border-t border-border px-4 py-3 text-sm text-muted-foreground">
        <span>
          Page {page.page} · Showing {page.items.length} of{" "}
          {page.total.toLocaleString("en-US")}
        </span>
        <div className="flex items-center gap-2">
          {prevHref ? (
            <Link
              href={prevHref}
              className="rounded-md border border-border px-2.5 py-1 text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              Previous
            </Link>
          ) : (
            <span className="rounded-md border border-border/50 px-2.5 py-1 text-muted-foreground/60">
              Previous
            </span>
          )}
          {nextHref ? (
            <Link
              href={nextHref}
              className="rounded-md border border-border px-2.5 py-1 text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              Next
            </Link>
          ) : (
            <span className="rounded-md border border-border/50 px-2.5 py-1 text-muted-foreground/60">
              Next
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
