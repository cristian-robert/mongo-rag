"use client";

import { KeyRound, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { ApiKey } from "@/lib/api-keys";

interface Props {
  keys: ApiKey[];
  onRevoke: (key: ApiKey) => void;
}

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

function formatDate(value: string | null): string {
  if (!value) return "Never";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown";
  return dateFormatter.format(date);
}

function formatRelative(value: string | null): string {
  if (!value) return "Never used";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown";
  const diffMs = Date.now() - date.getTime();
  const diffMin = Math.round(diffMs / 60000);
  if (diffMin < 1) return "Just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffH = Math.round(diffMin / 60);
  if (diffH < 24) return `${diffH}h ago`;
  const diffD = Math.round(diffH / 24);
  if (diffD < 30) return `${diffD}d ago`;
  return dateFormatter.format(date);
}

export function KeysTable({ keys, onRevoke }: Props) {
  if (keys.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border/70 bg-muted/30 px-8 py-14 text-center">
        <div className="flex size-10 items-center justify-center rounded-full border border-foreground/10 bg-background text-muted-foreground">
          <KeyRound className="size-4" />
        </div>
        <div className="space-y-1">
          <h3 className="font-heading text-base font-medium">No keys yet</h3>
          <p className="max-w-xs text-sm text-muted-foreground">
            Create your first API key to embed the chat widget or call the
            MongoRAG API from your own services.
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
            <th className="px-4 py-2.5 font-medium">Name</th>
            <th className="px-4 py-2.5 font-medium">Key</th>
            <th className="hidden px-4 py-2.5 font-medium md:table-cell">
              Permissions
            </th>
            <th className="hidden px-4 py-2.5 font-medium md:table-cell">
              Last used
            </th>
            <th className="hidden px-4 py-2.5 font-medium lg:table-cell">
              Created
            </th>
            <th className="px-4 py-2.5 font-medium">Status</th>
            <th className="px-4 py-2.5"></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border/60">
          {keys.map((key) => (
            <tr
              key={key.id}
              className="transition-colors hover:bg-muted/30"
              data-revoked={key.is_revoked || undefined}
            >
              <td className="px-4 py-3 font-medium">
                <div className="flex items-center gap-2">
                  <span className="truncate">{key.name}</span>
                </div>
              </td>
              <td className="px-4 py-3">
                <code className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-[0.75rem] text-muted-foreground">
                  mrag_{key.key_prefix}…
                </code>
              </td>
              <td className="hidden px-4 py-3 md:table-cell">
                <div className="flex flex-wrap gap-1">
                  {key.permissions.map((perm) => (
                    <Badge key={perm} variant="muted">
                      {perm}
                    </Badge>
                  ))}
                </div>
              </td>
              <td className="hidden px-4 py-3 text-muted-foreground md:table-cell">
                {formatRelative(key.last_used_at)}
              </td>
              <td className="hidden px-4 py-3 text-muted-foreground lg:table-cell">
                {formatDate(key.created_at)}
              </td>
              <td className="px-4 py-3">
                {key.is_revoked ? (
                  <Badge variant="destructive">Revoked</Badge>
                ) : (
                  <Badge variant="success">Active</Badge>
                )}
              </td>
              <td className="px-4 py-3 text-right">
                {!key.is_revoked && (
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`Revoke ${key.name}`}
                    onClick={() => onRevoke(key)}
                  >
                    <Trash2 />
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
