"use client";

import { Check, Copy, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { CreatedWebhook } from "@/lib/webhooks";

interface Props {
  webhook: CreatedWebhook | null;
  onClose: () => void;
}

export function RevealSecretDialog({ webhook, onClose }: Props) {
  const id = webhook?.id ?? null;
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const copied = !!id && copiedId === id;

  async function handleCopy() {
    if (!webhook) return;
    try {
      await navigator.clipboard.writeText(webhook.secret);
      setCopiedId(webhook.id);
      toast.success("Signing secret copied");
    } catch {
      toast.error("Could not copy — select and copy manually");
    }
  }

  return (
    <Dialog
      open={!!webhook}
      onOpenChange={(value) => {
        if (!value) onClose();
      }}
    >
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Save your signing secret</DialogTitle>
          <DialogDescription>
            Verify each delivery by computing{" "}
            <code className="font-mono text-xs">
              HMAC-SHA256(timestamp + &quot;.&quot; + raw_body)
            </code>{" "}
            with this secret and comparing it to the{" "}
            <code className="font-mono text-xs">X-MongoRAG-Signature</code>{" "}
            header. The secret is shown only once.
          </DialogDescription>
        </DialogHeader>

        <div
          role="alert"
          className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-800 dark:text-amber-200"
        >
          <ShieldAlert className="mt-0.5 size-4 shrink-0" />
          <span>
            Store this in your secrets manager. If lost, delete this webhook
            and create a new one.
          </span>
        </div>

        {webhook && (
          <div className="grid gap-3">
            <div className="flex items-stretch gap-2">
              <code
                className="grow truncate rounded-lg border border-border/60 bg-muted/40 px-3 py-2 font-mono text-xs"
                aria-label="Webhook signing secret"
              >
                {webhook.secret}
              </code>
              <Button
                type="button"
                variant="outline"
                onClick={handleCopy}
                aria-label="Copy signing secret"
              >
                {copied ? <Check /> : <Copy />}
                {copied ? "Copied" : "Copy"}
              </Button>
            </div>
            <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-xs text-muted-foreground">
              <dt>URL</dt>
              <dd className="truncate font-mono text-foreground">
                {webhook.url}
              </dd>
              <dt>Events</dt>
              <dd className="text-foreground">{webhook.events.join(", ")}</dd>
            </dl>
          </div>
        )}

        <DialogFooter>
          <Button onClick={onClose}>I&apos;ve stored it</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
