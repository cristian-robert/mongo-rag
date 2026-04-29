"use client";

import { useEffect, useState, useTransition } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Webhook, WebhookDelivery } from "@/lib/webhooks";

import { fetchDeliveriesAction } from "./fetch-deliveries-action";

interface Props {
  webhook: Webhook | null;
}

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: "short",
  timeStyle: "medium",
});

function formatDate(value: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return dateFormatter.format(d);
}

function statusVariant(
  status: WebhookDelivery["status"],
): "success" | "destructive" | "muted" {
  if (status === "delivered") return "success";
  if (status === "failed") return "destructive";
  return "muted";
}

function DeliveriesPanelInner({ webhook }: { webhook: Webhook }) {
  const [deliveries, setDeliveries] = useState<WebhookDelivery[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function refresh(): void {
    startTransition(async () => {
      const result = await fetchDeliveriesAction(webhook.id);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setError(null);
      setDeliveries(result.deliveries);
    });
  }

  useEffect(() => {
    let cancelled = false;
    startTransition(async () => {
      const result = await fetchDeliveriesAction(webhook.id);
      if (cancelled) return;
      if (!result.ok) {
        setError(result.error);
        setDeliveries([]);
        return;
      }
      setError(null);
      setDeliveries(result.deliveries);
    });
    return () => {
      cancelled = true;
    };
  }, [webhook.id]);

  return (
    <aside className="grid gap-3 rounded-xl border border-border/60 bg-card p-5">
      <header className="flex items-start justify-between gap-3">
        <div className="grid gap-0.5">
          <p className="font-mono text-[0.7rem] tracking-[0.2em] text-muted-foreground uppercase">
            Recent deliveries
          </p>
          <code className="truncate text-sm">{webhook.url}</code>
        </div>
        <Button
          variant="outline"
          size="sm"
          disabled={isPending}
          onClick={refresh}
        >
          {isPending ? "Loading…" : "Refresh"}
        </Button>
      </header>

      {error ? (
        <div
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive"
        >
          {error}
        </div>
      ) : deliveries.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {isPending ? "Loading deliveries…" : "No deliveries yet."}
        </p>
      ) : (
        <ul className="grid divide-y divide-border/60">
          {deliveries.map((d) => (
            <li
              key={d.id}
              className="grid gap-1 py-2.5 first:pt-0 last:pb-0"
            >
              <div className="flex items-center justify-between gap-2">
                <code className="truncate font-mono text-[0.78rem]">
                  {d.event}
                </code>
                <Badge variant={statusVariant(d.status)}>{d.status}</Badge>
              </div>
              <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
                <span>{formatDate(d.created_at)}</span>
                <span>
                  {d.attempts} {d.attempts === 1 ? "attempt" : "attempts"}
                </span>
                {d.response_code !== null && (
                  <span>HTTP {d.response_code}</span>
                )}
                {d.last_error && (
                  <span className="truncate text-destructive">
                    {d.last_error}
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}

export function DeliveriesPanel({ webhook }: Props) {
  if (!webhook) {
    return (
      <aside className="rounded-xl border border-dashed border-border/70 bg-muted/20 px-5 py-6 text-sm text-muted-foreground">
        Select a webhook to inspect recent delivery attempts.
      </aside>
    );
  }
  // Remount the inner panel when the selected webhook changes so its state
  // resets cleanly without a no-op effect branch.
  return <DeliveriesPanelInner key={webhook.id} webhook={webhook} />;
}
