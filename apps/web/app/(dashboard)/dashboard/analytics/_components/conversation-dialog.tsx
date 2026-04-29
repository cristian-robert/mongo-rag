"use client";

import { useRouter } from "next/navigation";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { ConversationDetail } from "@/lib/analytics";

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function ConversationDialog({
  detail,
  closeHref,
}: {
  detail: ConversationDetail;
  closeHref: string;
}) {
  const router = useRouter();

  return (
    <Dialog
      open
      onOpenChange={(next) => {
        if (!next) router.push(closeHref);
      }}
    >
      <DialogContent className="max-h-[85vh] w-[calc(100%-2rem)] max-w-2xl overflow-hidden p-0">
        <DialogHeader className="border-b border-border px-6 py-4">
          <DialogTitle className="font-heading text-base">
            Conversation transcript
          </DialogTitle>
          <DialogDescription>
            Session {detail.session_id.slice(0, 8)}… · started{" "}
            {formatTime(detail.created_at)}
          </DialogDescription>
        </DialogHeader>

        <div className="max-h-[60vh] overflow-y-auto px-6 py-4">
          {detail.messages.length === 0 ? (
            <p className="text-sm text-muted-foreground">No messages yet.</p>
          ) : (
            <ol className="flex flex-col gap-4">
              {detail.messages.map((m, i) => (
                <li
                  key={`${i}-${m.timestamp}`}
                  className="flex flex-col gap-1.5"
                >
                  <div className="flex items-center justify-between text-[0.72rem] uppercase tracking-wide text-muted-foreground">
                    <span className="font-medium">{m.role}</span>
                    <span className="tabular-nums">{formatTime(m.timestamp)}</span>
                  </div>
                  <div
                    className={
                      m.role === "user"
                        ? "rounded-lg border border-border bg-muted/40 px-3 py-2 text-sm text-foreground"
                        : "rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground"
                    }
                  >
                    <p className="whitespace-pre-wrap">{m.content}</p>
                    {m.sources.length > 0 ? (
                      <p className="mt-2 text-[0.72rem] text-muted-foreground">
                        Sources: {m.sources.join(", ")}
                      </p>
                    ) : null}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
