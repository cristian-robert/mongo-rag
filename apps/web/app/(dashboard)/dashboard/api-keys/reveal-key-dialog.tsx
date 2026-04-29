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
import type { CreatedApiKey } from "@/lib/api-keys";

interface Props {
  apiKey: CreatedApiKey | null;
  onClose: () => void;
}

export function RevealKeyDialog({ apiKey, onClose }: Props) {
  // Reset copied state whenever a new key is shown by keying state on the prefix.
  const keyId = apiKey?.key_prefix ?? null;
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const copied = !!keyId && copiedKey === keyId;

  async function handleCopy() {
    if (!apiKey) return;
    try {
      await navigator.clipboard.writeText(apiKey.raw_key);
      setCopiedKey(apiKey.key_prefix);
      toast.success("Key copied to clipboard");
    } catch {
      toast.error("Could not copy — select the key and copy manually");
    }
  }

  return (
    <Dialog
      open={!!apiKey}
      onOpenChange={(value) => {
        if (!value) onClose();
      }}
    >
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Save your API key</DialogTitle>
          <DialogDescription>
            This is the only time the full secret will be shown. Copy it now
            and store it in your secrets manager.
          </DialogDescription>
        </DialogHeader>

        <div
          role="alert"
          className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-800 dark:text-amber-200"
        >
          <ShieldAlert className="mt-0.5 size-4 shrink-0" />
          <span>
            We only store a hash of this key. If you lose it, revoke it and
            generate a new one.
          </span>
        </div>

        {apiKey && (
          <div className="grid gap-3">
            <div className="flex items-stretch gap-2">
              <code
                className="grow truncate rounded-lg border border-border/60 bg-muted/40 px-3 py-2 font-mono text-xs"
                aria-label="New API key"
              >
                {apiKey.raw_key}
              </code>
              <Button
                type="button"
                variant="outline"
                onClick={handleCopy}
                aria-label="Copy API key"
              >
                {copied ? <Check /> : <Copy />}
                {copied ? "Copied" : "Copy"}
              </Button>
            </div>
            <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-xs text-muted-foreground">
              <dt>Name</dt>
              <dd className="text-foreground">{apiKey.name}</dd>
              <dt>Permissions</dt>
              <dd className="text-foreground">
                {apiKey.permissions.join(", ")}
              </dd>
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
