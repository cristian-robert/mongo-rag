"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { Bot } from "@/lib/bots";
import {
  botPositions,
  botTones,
  createBotSchema,
  defaultBotFormValues,
  type CreateBotFormData,
} from "@/lib/validations/bots";

import { createBotAction, updateBotAction } from "./actions";

interface Props {
  mode: "create" | "edit";
  bot?: Bot;
}

const TONE_LABELS: Record<(typeof botTones)[number], string> = {
  professional: "Professional",
  friendly: "Friendly",
  concise: "Concise",
  technical: "Technical",
  playful: "Playful",
};

const POSITION_LABELS: Record<(typeof botPositions)[number], string> = {
  "bottom-right": "Bottom right",
  "bottom-left": "Bottom left",
};

function botToFormValues(bot: Bot): CreateBotFormData {
  return {
    name: bot.name,
    slug: bot.slug,
    description: bot.description ?? "",
    system_prompt: bot.system_prompt,
    welcome_message: bot.welcome_message,
    tone: bot.tone,
    is_public: bot.is_public,
    model_config: bot.model_config,
    widget_config: {
      primary_color: bot.widget_config.primary_color,
      position: bot.widget_config.position,
      avatar_url: bot.widget_config.avatar_url ?? undefined,
    },
    document_filter: bot.document_filter,
  };
}

export function BotForm({ mode, bot }: Props) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const form = useForm<CreateBotFormData>({
    resolver: zodResolver(createBotSchema),
    defaultValues: bot ? botToFormValues(bot) : defaultBotFormValues,
  });
  const temperature = useWatch({
    control: form.control,
    name: "model_config.temperature",
  });
  const docMode = useWatch({
    control: form.control,
    name: "document_filter.mode",
  });

  function onSubmit(data: CreateBotFormData) {
    startTransition(async () => {
      const result =
        mode === "create"
          ? await createBotAction(data)
          : await updateBotAction(bot!.id, data);

      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      toast.success(mode === "create" ? "Bot created" : "Bot updated");
      router.push(`/dashboard/bots/${result.bot.id}`);
      router.refresh();
    });
  }

  return (
    <form
      onSubmit={form.handleSubmit(onSubmit)}
      className="space-y-8"
      noValidate
    >
      <section className="space-y-4 rounded-xl border border-border/60 bg-card p-5">
        <header className="space-y-1">
          <h2 className="text-base font-medium">Identity</h2>
          <p className="text-sm text-muted-foreground">
            How customers see and refer to this bot.
          </p>
        </header>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="grid gap-1.5">
            <Label htmlFor="bot-name">Name</Label>
            <Input
              id="bot-name"
              placeholder="Support Bot"
              autoComplete="off"
              aria-invalid={!!form.formState.errors.name}
              {...form.register("name")}
            />
            {form.formState.errors.name && (
              <p className="text-xs text-destructive" role="alert">
                {form.formState.errors.name.message}
              </p>
            )}
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="bot-slug">Slug</Label>
            <Input
              id="bot-slug"
              placeholder="support-bot"
              autoComplete="off"
              disabled={mode === "edit"}
              aria-invalid={!!form.formState.errors.slug}
              {...form.register("slug")}
            />
            {form.formState.errors.slug ? (
              <p className="text-xs text-destructive" role="alert">
                {form.formState.errors.slug.message}
              </p>
            ) : (
              <p className="text-xs text-muted-foreground">
                Used in embed URLs. Cannot be changed once set.
              </p>
            )}
          </div>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="bot-description">Description (optional)</Label>
          <Textarea
            id="bot-description"
            placeholder="Helps shoppers with order status, returns, and product questions."
            rows={2}
            {...form.register("description")}
          />
        </div>
      </section>

      <section className="space-y-4 rounded-xl border border-border/60 bg-card p-5">
        <header className="space-y-1">
          <h2 className="text-base font-medium">Behavior</h2>
          <p className="text-sm text-muted-foreground">
            Control the bot&apos;s personality and what it tells visitors first.
          </p>
        </header>
        <div className="grid gap-1.5">
          <Label htmlFor="bot-system-prompt">System prompt</Label>
          <Textarea
            id="bot-system-prompt"
            rows={6}
            aria-invalid={!!form.formState.errors.system_prompt}
            {...form.register("system_prompt")}
          />
          {form.formState.errors.system_prompt && (
            <p className="text-xs text-destructive" role="alert">
              {form.formState.errors.system_prompt.message}
            </p>
          )}
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="grid gap-1.5">
            <Label htmlFor="bot-welcome">Welcome message</Label>
            <Input
              id="bot-welcome"
              {...form.register("welcome_message")}
              aria-invalid={!!form.formState.errors.welcome_message}
            />
            {form.formState.errors.welcome_message && (
              <p className="text-xs text-destructive" role="alert">
                {form.formState.errors.welcome_message.message}
              </p>
            )}
          </div>
          <Controller
            control={form.control}
            name="tone"
            render={({ field }) => (
              <div className="grid gap-1.5">
                <Label htmlFor="bot-tone">Tone</Label>
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id="bot-tone">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {botTones.map((tone) => (
                      <SelectItem key={tone} value={tone}>
                        {TONE_LABELS[tone]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="grid gap-1.5">
            <Label htmlFor="bot-temperature">
              Temperature ({(temperature ?? 0).toFixed(2)})
            </Label>
            <input
              id="bot-temperature"
              type="range"
              min={0}
              max={1}
              step={0.05}
              {...form.register("model_config.temperature", {
                valueAsNumber: true,
              })}
              className="accent-foreground"
            />
            <p className="text-xs text-muted-foreground">
              Lower is focused; higher is creative.
            </p>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="bot-max-tokens">Max tokens per reply</Label>
            <Input
              id="bot-max-tokens"
              type="number"
              min={64}
              max={8192}
              {...form.register("model_config.max_tokens", {
                valueAsNumber: true,
              })}
            />
          </div>
        </div>
      </section>

      <section className="space-y-4 rounded-xl border border-border/60 bg-card p-5">
        <header className="space-y-1">
          <h2 className="text-base font-medium">Sources</h2>
          <p className="text-sm text-muted-foreground">
            Restrict the bot to a subset of your documents — or let it search
            the full corpus.
          </p>
        </header>
        <Controller
          control={form.control}
          name="document_filter.mode"
          render={({ field }) => (
            <div className="grid gap-1.5">
              <Label htmlFor="bot-doc-mode">Document scope</Label>
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger id="bot-doc-mode">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">
                    All documents in the workspace
                  </SelectItem>
                  <SelectItem value="ids">Specific document IDs</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}
        />
        {docMode === "ids" && (
          <Controller
            control={form.control}
            name="document_filter.document_ids"
            render={({ field }) => (
              <div className="grid gap-1.5">
                <Label htmlFor="bot-doc-ids">Document IDs</Label>
                <Textarea
                  id="bot-doc-ids"
                  rows={3}
                  placeholder="Comma- or newline-separated IDs"
                  defaultValue={field.value?.join("\n") ?? ""}
                  onChange={(e) => {
                    const ids = e.target.value
                      .split(/[\s,]+/)
                      .map((s) => s.trim())
                      .filter(Boolean);
                    field.onChange(ids);
                  }}
                />
                <p className="text-xs text-muted-foreground">
                  {field.value?.length ?? 0} ID
                  {field.value?.length === 1 ? "" : "s"} listed.
                </p>
              </div>
            )}
          />
        )}
      </section>

      <section className="space-y-4 rounded-xl border border-border/60 bg-card p-5">
        <header className="space-y-1">
          <h2 className="text-base font-medium">Widget</h2>
          <p className="text-sm text-muted-foreground">
            Look-and-feel of the embedded chat bubble.
          </p>
        </header>
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="grid gap-1.5">
            <Label htmlFor="bot-color">Primary color</Label>
            <Input
              id="bot-color"
              type="color"
              {...form.register("widget_config.primary_color")}
              className="h-9 w-full p-1"
            />
          </div>
          <Controller
            control={form.control}
            name="widget_config.position"
            render={({ field }) => (
              <div className="grid gap-1.5">
                <Label htmlFor="bot-position">Position</Label>
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id="bot-position">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {botPositions.map((pos) => (
                      <SelectItem key={pos} value={pos}>
                        {POSITION_LABELS[pos]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          />
          <div className="grid gap-1.5">
            <Label htmlFor="bot-avatar">Avatar URL (https)</Label>
            <Input
              id="bot-avatar"
              type="url"
              placeholder="https://…"
              {...form.register("widget_config.avatar_url")}
            />
            {form.formState.errors.widget_config?.avatar_url && (
              <p className="text-xs text-destructive" role="alert">
                {form.formState.errors.widget_config.avatar_url.message}
              </p>
            )}
          </div>
        </div>
      </section>

      <section className="space-y-4 rounded-xl border border-border/60 bg-card p-5">
        <header className="space-y-1">
          <h2 className="text-base font-medium">Visibility</h2>
          <p className="text-sm text-muted-foreground">
            Public bots expose only their non-secret config (name, color,
            welcome message) so the widget can bootstrap without an API key.
            The system prompt and document scope stay private. The chat
            endpoint always requires an API key.
          </p>
        </header>
        <Controller
          control={form.control}
          name="is_public"
          render={({ field }) => (
            <Label
              htmlFor="bot-public"
              className="flex cursor-pointer items-start gap-2.5 rounded-lg border border-border/60 bg-muted/20 px-3 py-2 transition-colors has-aria-checked:border-foreground/30 has-aria-checked:bg-muted/60"
            >
              <Checkbox
                id="bot-public"
                checked={field.value}
                onCheckedChange={(v) => field.onChange(Boolean(v))}
              />
              <span className="grid gap-0.5 text-sm leading-tight">
                <span className="font-medium">Allow public widget bootstrap</span>
                <span className="text-xs text-muted-foreground">
                  Required if you want to embed the widget without proxying
                  the bot config through your own server.
                </span>
              </span>
            </Label>
          )}
        />
      </section>

      <div className="flex items-center justify-end gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={() => router.back()}
          disabled={isPending}
        >
          Cancel
        </Button>
        <Button type="submit" disabled={isPending}>
          {isPending
            ? "Saving…"
            : mode === "create"
              ? "Create bot"
              : "Save changes"}
        </Button>
      </div>
    </form>
  );
}
