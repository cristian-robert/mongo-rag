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
import type { ApiKey } from "@/lib/api-keys";

interface Props {
  apiKey: ApiKey | null;
  onCancel: () => void;
  onConfirm: () => void;
  isPending: boolean;
}

export function RevokeKeyDialog({
  apiKey,
  onCancel,
  onConfirm,
  isPending,
}: Props) {
  return (
    <Dialog
      open={!!apiKey}
      onOpenChange={(value) => {
        if (!value) onCancel();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Revoke this API key?</DialogTitle>
          <DialogDescription>
            Any service or widget using this key will start failing
            immediately. This cannot be undone — generate a new key if you
            need access again.
          </DialogDescription>
        </DialogHeader>
        {apiKey && (
          <p className="rounded-lg border border-border/60 bg-muted/40 px-3 py-2 text-sm">
            <span className="font-medium">{apiKey.name}</span>{" "}
            <code className="ml-1 font-mono text-xs text-muted-foreground">
              mrag_{apiKey.key_prefix}…
            </code>
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
            {isPending ? "Revoking…" : "Revoke key"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
