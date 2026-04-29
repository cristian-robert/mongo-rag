"use client";

import Link from "next/link";
import { Bot as BotIcon, Pencil, Trash2 } from "lucide-react";
import { useTransition } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Bot } from "@/lib/bots";

import { deleteBotAction } from "./actions";

interface Props {
  bots: Bot[];
}

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
});

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown";
  return dateFormatter.format(date);
}

export function BotsTable({ bots }: Props) {
  const [isPending, startTransition] = useTransition();

  function handleDelete(bot: Bot) {
    if (
      !window.confirm(
        `Delete bot "${bot.name}"? Existing embed snippets will stop working.`,
      )
    ) {
      return;
    }
    startTransition(async () => {
      const result = await deleteBotAction(bot.id);
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      toast.success(`Deleted "${bot.name}"`);
    });
  }

  if (bots.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border/70 bg-muted/30 px-8 py-14 text-center">
        <div className="flex size-10 items-center justify-center rounded-full border border-foreground/10 bg-background text-muted-foreground">
          <BotIcon className="size-4" />
        </div>
        <div className="space-y-1">
          <h3 className="font-heading text-base font-medium">No bots yet</h3>
          <p className="max-w-xs text-sm text-muted-foreground">
            Create a bot to give it a personality, scope its document sources,
            and generate an embed snippet.
          </p>
        </div>
        <Button
          render={(props) => (
            <Link {...props} href="/dashboard/bots/new">
              Create your first bot
            </Link>
          )}
        />
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
      <table className="w-full text-sm">
        <thead className="border-b border-border/60 bg-muted/40 text-left text-[0.7rem] tracking-wide text-muted-foreground uppercase">
          <tr>
            <th className="px-4 py-2.5 font-medium">Name</th>
            <th className="px-4 py-2.5 font-medium">Slug</th>
            <th className="hidden px-4 py-2.5 font-medium md:table-cell">
              Tone
            </th>
            <th className="hidden px-4 py-2.5 font-medium md:table-cell">
              Visibility
            </th>
            <th className="hidden px-4 py-2.5 font-medium lg:table-cell">
              Created
            </th>
            <th className="px-4 py-2.5"></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border/60">
          {bots.map((bot) => (
            <tr key={bot.id} className="transition-colors hover:bg-muted/30">
              <td className="px-4 py-3 font-medium">
                <Link
                  href={`/dashboard/bots/${bot.id}`}
                  className="hover:underline"
                >
                  {bot.name}
                </Link>
                {bot.description && (
                  <p className="max-w-md truncate text-xs text-muted-foreground">
                    {bot.description}
                  </p>
                )}
              </td>
              <td className="px-4 py-3">
                <code className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-[0.75rem] text-muted-foreground">
                  {bot.slug}
                </code>
              </td>
              <td className="hidden px-4 py-3 md:table-cell">
                <Badge variant="muted">{bot.tone}</Badge>
              </td>
              <td className="hidden px-4 py-3 md:table-cell">
                {bot.is_public ? (
                  <Badge variant="success">Public</Badge>
                ) : (
                  <Badge variant="muted">Private</Badge>
                )}
              </td>
              <td className="hidden px-4 py-3 text-muted-foreground lg:table-cell">
                {formatDate(bot.created_at)}
              </td>
              <td className="px-4 py-3 text-right">
                <div className="inline-flex gap-1">
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`Edit ${bot.name}`}
                    render={(props) => (
                      <Link {...props} href={`/dashboard/bots/${bot.id}`} />
                    )}
                  >
                    <Pencil />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`Delete ${bot.name}`}
                    disabled={isPending}
                    onClick={() => handleDelete(bot)}
                  >
                    <Trash2 />
                  </Button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
