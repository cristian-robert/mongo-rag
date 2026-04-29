"use client";

import { Plus } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import type { CreatedWebhook, Webhook } from "@/lib/webhooks";
import type { CreateWebhookFormData } from "@/lib/validations/webhooks";

import {
  createWebhookAction,
  deleteWebhookAction,
  testFireWebhookAction,
  toggleWebhookAction,
} from "./actions";
import { CreateWebhookDialog } from "./create-webhook-dialog";
import { DeleteWebhookDialog } from "./delete-webhook-dialog";
import { DeliveriesPanel } from "./deliveries-panel";
import { RevealSecretDialog } from "./reveal-secret-dialog";
import { WebhooksTable } from "./webhooks-table";

interface Props {
  initialWebhooks: Webhook[];
  initialError: string | null;
}

export function WebhooksClient({ initialWebhooks, initialError }: Props) {
  const [webhooks, setWebhooks] = useState<Webhook[]>(initialWebhooks);
  const [createOpen, setCreateOpen] = useState(false);
  const [reveal, setReveal] = useState<CreatedWebhook | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Webhook | null>(null);
  const [selected, setSelected] = useState<Webhook | null>(
    initialWebhooks[0] ?? null,
  );
  const [busyId, setBusyId] = useState<string | null>(null);
  const [, startTransition] = useTransition();

  function handleCreate(input: CreateWebhookFormData) {
    startTransition(async () => {
      const result = await createWebhookAction(input);
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      const created = result.webhook;
      setWebhooks((prev) => [
        {
          id: created.id,
          url: created.url,
          events: created.events,
          description: created.description,
          active: created.active,
          secret_prefix: created.secret_prefix,
          created_at: created.created_at,
          updated_at: created.updated_at,
        },
        ...prev,
      ]);
      setCreateOpen(false);
      setReveal(created);
      setSelected({
        id: created.id,
        url: created.url,
        events: created.events,
        description: created.description,
        active: created.active,
        secret_prefix: created.secret_prefix,
        created_at: created.created_at,
        updated_at: created.updated_at,
      });
    });
  }

  function handleDelete() {
    if (!deleteTarget) return;
    const target = deleteTarget;
    setBusyId(target.id);
    startTransition(async () => {
      const result = await deleteWebhookAction(target.id);
      setBusyId(null);
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      toast.success("Webhook deleted");
      setWebhooks((prev) => prev.filter((w) => w.id !== target.id));
      if (selected?.id === target.id) setSelected(null);
      setDeleteTarget(null);
    });
  }

  function handleToggle(webhook: Webhook) {
    setBusyId(webhook.id);
    startTransition(async () => {
      const result = await toggleWebhookAction(webhook.id, !webhook.active);
      setBusyId(null);
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      setWebhooks((prev) =>
        prev.map((w) =>
          w.id === webhook.id ? { ...w, active: !w.active } : w,
        ),
      );
      toast.success(webhook.active ? "Webhook paused" : "Webhook resumed");
    });
  }

  function handleTest(webhook: Webhook) {
    const event = webhook.events[0];
    if (!event) return;
    setBusyId(webhook.id);
    startTransition(async () => {
      const result = await testFireWebhookAction({
        webhookId: webhook.id,
        event,
      });
      setBusyId(null);
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      toast.success(`Test ${event} delivered — check the recent deliveries`);
      // Refocus the panel on this webhook so the user sees the new attempt.
      setSelected(webhook);
    });
  }

  return (
    <section className="grid gap-6">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {webhooks.length === 0 && !initialError
            ? "No webhooks yet."
            : `${webhooks.length} ${webhooks.length === 1 ? "webhook" : "webhooks"}`}
        </p>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus />
          New webhook
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
        <WebhooksTable
          webhooks={webhooks}
          busyId={busyId}
          selectedId={selected?.id ?? null}
          onDelete={setDeleteTarget}
          onToggle={handleToggle}
          onTest={handleTest}
          onSelect={setSelected}
        />
      )}

      <DeliveriesPanel webhook={selected} />

      <CreateWebhookDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onSubmit={handleCreate}
        isPending={busyId !== null}
      />

      <RevealSecretDialog webhook={reveal} onClose={() => setReveal(null)} />

      <DeleteWebhookDialog
        webhook={deleteTarget}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
        isPending={busyId === deleteTarget?.id}
      />
    </section>
  );
}
