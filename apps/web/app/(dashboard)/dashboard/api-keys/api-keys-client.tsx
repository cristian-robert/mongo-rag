"use client";

import { Plus } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import type { ApiKey, CreatedApiKey } from "@/lib/api-keys";

import { CreateKeyDialog } from "./create-key-dialog";
import { KeysTable } from "./keys-table";
import { RevealKeyDialog } from "./reveal-key-dialog";
import { RevokeKeyDialog } from "./revoke-key-dialog";
import {
  createApiKeyAction,
  revokeApiKeyAction,
} from "./actions";

interface Props {
  initialKeys: ApiKey[];
  initialError: string | null;
}

export function ApiKeysClient({ initialKeys, initialError }: Props) {
  const [createOpen, setCreateOpen] = useState(false);
  const [revealKey, setRevealKey] = useState<CreatedApiKey | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<ApiKey | null>(null);
  const [isPending, startTransition] = useTransition();

  function handleCreate(input: { name: string; permissions: ("chat" | "search")[] }) {
    startTransition(async () => {
      const result = await createApiKeyAction(input);
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      setCreateOpen(false);
      setRevealKey(result.key);
    });
  }

  function handleRevoke() {
    if (!revokeTarget) return;
    const target = revokeTarget;
    startTransition(async () => {
      const result = await revokeApiKeyAction(target.id);
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      toast.success(`Revoked "${target.name}"`);
      setRevokeTarget(null);
    });
  }

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {initialKeys.length === 0 && !initialError
            ? "No keys yet."
            : `${initialKeys.length} ${initialKeys.length === 1 ? "key" : "keys"}`}
        </p>
        <Button onClick={() => setCreateOpen(true)} disabled={isPending}>
          <Plus />
          New key
        </Button>
      </div>

      {initialError ? (
        <div
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive"
        >
          {initialError}
        </div>
      ) : (
        <KeysTable keys={initialKeys} onRevoke={setRevokeTarget} />
      )}

      <CreateKeyDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onSubmit={handleCreate}
        isPending={isPending}
      />

      <RevealKeyDialog
        apiKey={revealKey}
        onClose={() => setRevealKey(null)}
      />

      <RevokeKeyDialog
        apiKey={revokeTarget}
        onCancel={() => setRevokeTarget(null)}
        onConfirm={handleRevoke}
        isPending={isPending}
      />
    </section>
  );
}
