"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { Controller, useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  createWebhookSchema,
  webhookEvents,
  type CreateWebhookFormData,
} from "@/lib/validations/webhooks";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (input: CreateWebhookFormData) => void;
  isPending: boolean;
}

const EVENT_LABELS: Record<(typeof webhookEvents)[number], string> = {
  "document.ingested": "Document ingested — fires after a document is embedded",
  "document.deleted": "Document deleted — fires after a document is removed",
  "chat.completed": "Chat completed — fires after a conversation turn finishes",
  "subscription.updated": "Subscription updated — billing plan or status changed",
};

export function CreateWebhookDialog({
  open,
  onOpenChange,
  onSubmit,
  isPending,
}: Props) {
  const form = useForm<CreateWebhookFormData>({
    resolver: zodResolver(createWebhookSchema),
    defaultValues: {
      url: "",
      events: ["document.ingested"],
      description: "",
      active: true,
    },
  });

  useEffect(() => {
    if (!open) {
      form.reset({
        url: "",
        events: ["document.ingested"],
        description: "",
        active: true,
      });
    }
  }, [open, form]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>New webhook</DialogTitle>
          <DialogDescription>
            Receive HMAC-signed POSTs when events happen in your tenant. The
            signing secret is shown once after creation — store it carefully.
          </DialogDescription>
        </DialogHeader>

        <form
          className="grid gap-4"
          onSubmit={form.handleSubmit(onSubmit)}
          noValidate
        >
          <div className="grid gap-1.5">
            <Label htmlFor="webhook-url">Endpoint URL</Label>
            <Input
              id="webhook-url"
              placeholder="https://example.com/hooks/mongorag"
              autoComplete="off"
              autoFocus
              aria-invalid={!!form.formState.errors.url}
              {...form.register("url")}
            />
            {form.formState.errors.url && (
              <p className="text-xs text-destructive" role="alert">
                {form.formState.errors.url.message}
              </p>
            )}
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="webhook-description">
              Description{" "}
              <span className="text-muted-foreground">(optional)</span>
            </Label>
            <Input
              id="webhook-description"
              placeholder="Production audit log"
              autoComplete="off"
              {...form.register("description")}
            />
            {form.formState.errors.description && (
              <p className="text-xs text-destructive" role="alert">
                {form.formState.errors.description.message}
              </p>
            )}
          </div>

          <Controller
            control={form.control}
            name="events"
            render={({ field }) => (
              <fieldset className="grid gap-2">
                <legend className="text-sm font-medium">Events</legend>
                {webhookEvents.map((event) => {
                  const checked = field.value?.includes(event) ?? false;
                  return (
                    <Label
                      key={event}
                      htmlFor={`event-${event}`}
                      className="flex cursor-pointer items-start gap-2.5 rounded-lg border border-border/60 bg-muted/20 px-3 py-2 transition-colors has-aria-checked:border-foreground/30 has-aria-checked:bg-muted/60"
                    >
                      <Checkbox
                        id={`event-${event}`}
                        checked={checked}
                        onCheckedChange={(value) => {
                          const next = new Set(field.value ?? []);
                          if (value) next.add(event);
                          else next.delete(event);
                          field.onChange(Array.from(next));
                        }}
                      />
                      <span className="grid gap-0.5 text-sm leading-tight">
                        <span className="font-mono text-[0.8rem] font-medium">
                          {event}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {EVENT_LABELS[event]}
                        </span>
                      </span>
                    </Label>
                  );
                })}
                {form.formState.errors.events && (
                  <p className="text-xs text-destructive" role="alert">
                    {form.formState.errors.events.message as string}
                  </p>
                )}
              </fieldset>
            )}
          />

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isPending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? "Creating…" : "Create webhook"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
