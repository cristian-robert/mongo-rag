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
  apiKeyPermissions,
  createApiKeySchema,
  type CreateApiKeyFormData,
} from "@/lib/validations/api-keys";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (input: CreateApiKeyFormData) => void;
  isPending: boolean;
}

const PERMISSION_LABELS: Record<(typeof apiKeyPermissions)[number], string> = {
  chat: "Chat — answer questions via the agent",
  search: "Search — query documents directly",
};

export function CreateKeyDialog({ open, onOpenChange, onSubmit, isPending }: Props) {
  const form = useForm<CreateApiKeyFormData>({
    resolver: zodResolver(createApiKeySchema),
    defaultValues: { name: "", permissions: ["chat", "search"] },
  });

  useEffect(() => {
    if (!open) form.reset({ name: "", permissions: ["chat", "search"] });
  }, [open, form]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create API key</DialogTitle>
          <DialogDescription>
            Give the key a recognisable name. The full secret is shown only once
            after it is created — store it somewhere safe.
          </DialogDescription>
        </DialogHeader>

        <form
          className="grid gap-4"
          onSubmit={form.handleSubmit(onSubmit)}
          noValidate
        >
          <div className="grid gap-1.5">
            <Label htmlFor="api-key-name">Name</Label>
            <Input
              id="api-key-name"
              placeholder="Production widget"
              autoComplete="off"
              autoFocus
              aria-invalid={!!form.formState.errors.name}
              {...form.register("name")}
            />
            {form.formState.errors.name && (
              <p
                className="text-xs text-destructive"
                role="alert"
                id="api-key-name-error"
              >
                {form.formState.errors.name.message}
              </p>
            )}
          </div>

          <Controller
            control={form.control}
            name="permissions"
            render={({ field }) => (
              <fieldset className="grid gap-2">
                <legend className="text-sm font-medium">Permissions</legend>
                {apiKeyPermissions.map((perm) => {
                  const checked = field.value?.includes(perm) ?? false;
                  return (
                    <Label
                      key={perm}
                      htmlFor={`perm-${perm}`}
                      className="flex cursor-pointer items-start gap-2.5 rounded-lg border border-border/60 bg-muted/20 px-3 py-2 transition-colors has-aria-checked:border-foreground/30 has-aria-checked:bg-muted/60"
                    >
                      <Checkbox
                        id={`perm-${perm}`}
                        checked={checked}
                        onCheckedChange={(value) => {
                          const next = new Set(field.value ?? []);
                          if (value) next.add(perm);
                          else next.delete(perm);
                          field.onChange(Array.from(next));
                        }}
                      />
                      <span className="grid gap-0.5 text-sm leading-tight">
                        <span className="font-medium capitalize">{perm}</span>
                        <span className="text-xs text-muted-foreground">
                          {PERMISSION_LABELS[perm]}
                        </span>
                      </span>
                    </Label>
                  );
                })}
                {form.formState.errors.permissions && (
                  <p className="text-xs text-destructive" role="alert">
                    {form.formState.errors.permissions.message as string}
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
              {isPending ? "Creating…" : "Create key"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
