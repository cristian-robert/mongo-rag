"use client";

import { Trash2, Webhook as WebhookIcon, Zap } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Webhook } from "@/lib/webhooks";

interface Props {
  webhooks: Webhook[];
  busyId: string | null;
  onDelete: (webhook: Webhook) => void;
  onToggle: (webhook: Webhook) => void;
  onTest: (webhook: Webhook) => void;
  onSelect: (webhook: Webhook) => void;
  selectedId: string | null;
}

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

function formatDate(value: string): string {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return dateFormatter.format(d);
}

export function WebhooksTable({
  webhooks,
  busyId,
  onDelete,
  onToggle,
  onTest,
  onSelect,
  selectedId,
}: Props) {
  if (webhooks.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border/70 bg-muted/30 px-8 py-14 text-center">
        <div className="flex size-10 items-center justify-center rounded-full border border-foreground/10 bg-background text-muted-foreground">
          <WebhookIcon className="size-4" />
        </div>
        <div className="space-y-1">
          <h3 className="font-heading text-base font-medium">
            No webhooks yet
          </h3>
          <p className="max-w-sm text-sm text-muted-foreground">
            Subscribe an HTTPS endpoint to events like document ingestion or
            chat completion. Each delivery is HMAC-signed and retried with
            backoff.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
      <table className="w-full text-sm">
        <thead className="border-b border-border/60 bg-muted/40 text-left text-[0.7rem] tracking-wide text-muted-foreground uppercase">
          <tr>
            <th className="px-4 py-2.5 font-medium">URL</th>
            <th className="hidden px-4 py-2.5 font-medium lg:table-cell">
              Events
            </th>
            <th className="hidden px-4 py-2.5 font-medium md:table-cell">
              Created
            </th>
            <th className="px-4 py-2.5 font-medium">Status</th>
            <th className="px-4 py-2.5 text-right font-medium">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border/60">
          {webhooks.map((w) => {
            const busy = busyId === w.id;
            const selected = selectedId === w.id;
            return (
              <tr
                key={w.id}
                aria-current={selected || undefined}
                onClick={() => onSelect(w)}
                className="cursor-pointer transition-colors hover:bg-muted/30 aria-current:bg-muted/40"
              >
                <td className="px-4 py-3">
                  <div className="grid gap-0.5">
                    <code className="truncate font-mono text-[0.8rem]">
                      {w.url}
                    </code>
                    {w.description && (
                      <span className="truncate text-xs text-muted-foreground">
                        {w.description}
                      </span>
                    )}
                  </div>
                </td>
                <td className="hidden px-4 py-3 lg:table-cell">
                  <div className="flex flex-wrap gap-1">
                    {w.events.map((e) => (
                      <Badge key={e} variant="muted">
                        {e}
                      </Badge>
                    ))}
                  </div>
                </td>
                <td className="hidden px-4 py-3 text-muted-foreground md:table-cell">
                  {formatDate(w.created_at)}
                </td>
                <td className="px-4 py-3">
                  {w.active ? (
                    <Badge variant="success">Active</Badge>
                  ) : (
                    <Badge variant="muted">Paused</Badge>
                  )}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center justify-end gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={busy}
                      aria-label={`Send test event to ${w.url}`}
                      onClick={(ev) => {
                        ev.stopPropagation();
                        onTest(w);
                      }}
                    >
                      <Zap className="size-3.5" />
                      Test
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={busy}
                      onClick={(ev) => {
                        ev.stopPropagation();
                        onToggle(w);
                      }}
                    >
                      {w.active ? "Pause" : "Resume"}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      disabled={busy}
                      aria-label={`Delete webhook ${w.url}`}
                      onClick={(ev) => {
                        ev.stopPropagation();
                        onDelete(w);
                      }}
                    >
                      <Trash2 />
                    </Button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
