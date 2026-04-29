"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { Webhook } from "@/lib/webhooks";

interface Props {
  webhook: Webhook | null;
  onCancel: () => void;
  onConfirm: () => void;
  isPending: boolean;
}

export function DeleteWebhookDialog({
  webhook,
  onCancel,
  onConfirm,
  isPending,
}: Props) {
  return (
    <Dialog
      open={!!webhook}
      onOpenChange={(value) => {
        if (!value) onCancel();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete this webhook?</DialogTitle>
          <DialogDescription>
            We will stop delivering events to this endpoint immediately. The
            signing secret is destroyed — to re-enable, create a new webhook.
          </DialogDescription>
        </DialogHeader>
        {webhook && (
          <p className="rounded-lg border border-border/60 bg-muted/40 px-3 py-2 text-sm">
            <code className="font-mono text-xs">{webhook.url}</code>
          </p>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onCancel} disabled={isPending}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={onConfirm}
            disabled={isPending}
          >
            {isPending ? "Deleting…" : "Delete webhook"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
