import type { UsageResponse } from "@/lib/billing";

import { UsageRow } from "./usage-row";

export function UsagePanel({
  usage,
  loadError,
}: {
  usage: UsageResponse | null;
  loadError: string | null;
}) {
  return (
    <section
      aria-labelledby="usage-heading"
      className="flex flex-col gap-4 rounded-xl border border-border bg-card p-5 text-card-foreground"
    >
      <header className="flex flex-col gap-1">
        <p className="font-mono text-[0.7rem] tracking-[0.2em] text-muted-foreground uppercase">
          This period
        </p>
        <h2
          id="usage-heading"
          className="font-heading text-base font-medium tracking-tight"
        >
          Usage vs. plan limits
        </h2>
      </header>

      {loadError || !usage ? (
        <p
          role="status"
          className="rounded-md border border-border bg-muted/40 px-3 py-2 text-[0.78rem] text-muted-foreground"
        >
          {loadError ?? "Usage data is not available right now."}
        </p>
      ) : (
        <div className="flex flex-col gap-4">
          <UsageRow
            label="Queries"
            used={usage.queries.used}
            limit={usage.queries.limit}
            warning={usage.queries.warning}
            blocked={usage.queries.blocked}
            unit="this month"
          />
          <UsageRow
            label="Documents"
            used={usage.documents.used}
            limit={usage.documents.limit}
            warning={usage.documents.warning}
            blocked={usage.documents.blocked}
          />
          <UsageRow
            label="Chunks"
            used={usage.chunks.used}
            limit={usage.chunks.limit}
            warning={usage.chunks.warning}
            blocked={usage.chunks.blocked}
          />
          <UsageRow
            label="Embedding tokens"
            used={usage.embedding_tokens.used}
            limit={usage.embedding_tokens.limit}
            warning={usage.embedding_tokens.warning}
            blocked={usage.embedding_tokens.blocked}
            unit="this month"
          />
        </div>
      )}
    </section>
  );
}
