"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useRef, useState, useTransition } from "react";
import {
  Controller,
  useForm,
  useWatch,
  type Control,
  type FieldPath,
  type Resolver,
  type UseFormReturn,
} from "react-hook-form";
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
  colorModes,
  createBotSchema,
  defaultBotFormValues,
  densityTokens,
  launcherIcons,
  launcherShapes,
  radiusTokens,
  sizeTokens,
  type CreateBotFormData,
} from "@/lib/validations/bots";
import { contrastRatio, wcagGrade } from "@/lib/contrast";
import { WIDGET_FONTS, WIDGET_FONT_KEYS } from "@/lib/widget-fonts";

import { createBotAction, updateBotAction } from "./actions";
import { AntiSlopAside } from "./anti-slop-aside";
import { PresetRow } from "./preset-row";
import { PreviewPane } from "./preview-pane";
import { type ThemePreset } from "./presets";

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

const COLOR_MODE_LABELS: Record<(typeof colorModes)[number], string> = {
  light: "Light",
  dark: "Dark",
  auto: "Match system",
};

const RADIUS_LABELS: Record<(typeof radiusTokens)[number], string> = {
  none: "None (sharp)",
  sm: "Small",
  md: "Medium",
  lg: "Large",
  full: "Pill",
};

const DENSITY_LABELS: Record<(typeof densityTokens)[number], string> = {
  compact: "Compact",
  comfortable: "Comfortable",
  spacious: "Spacious",
};

const SIZE_LABELS: Record<(typeof sizeTokens)[number], string> = {
  sm: "Small",
  md: "Medium",
  lg: "Large",
};

const LAUNCHER_SHAPE_LABELS: Record<(typeof launcherShapes)[number], string> = {
  circle: "Circle",
  "rounded-square": "Rounded square",
  pill: "Pill",
};

const LAUNCHER_ICON_LABELS: Record<(typeof launcherIcons)[number], string> = {
  chat: "Chat bubble",
  sparkle: "Sparkle",
  book: "Book",
  question: "Question mark",
  custom: "Custom URL",
};

function botToFormValues(bot: Bot): CreateBotFormData {
  const w = bot.widget_config;
  const dark = w.dark_overrides;
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
      primary_color: w.primary_color,
      position: w.position,
      avatar_url: w.avatar_url ?? undefined,
      color_mode: w.color_mode ?? "light",
      background: w.background ?? undefined,
      surface: w.surface ?? undefined,
      foreground: w.foreground ?? undefined,
      muted: w.muted ?? undefined,
      border: w.border ?? undefined,
      primary_foreground: w.primary_foreground ?? "#ffffff",
      dark_overrides: dark
        ? {
            background: dark.background ?? undefined,
            surface: dark.surface ?? undefined,
            foreground: dark.foreground ?? undefined,
            muted: dark.muted ?? undefined,
            border: dark.border ?? undefined,
            primary: dark.primary ?? undefined,
            primary_foreground: dark.primary_foreground ?? undefined,
          }
        : undefined,
      font_family: (w.font_family ??
        "system") as CreateBotFormData["widget_config"]["font_family"],
      display_font:
        (w.display_font as CreateBotFormData["widget_config"]["display_font"]) ?? undefined,
      base_font_size: w.base_font_size ?? "md",
      radius: w.radius ?? "md",
      density: w.density ?? "comfortable",
      launcher_shape: w.launcher_shape ?? "circle",
      launcher_size: w.launcher_size ?? "md",
      panel_size: w.panel_size ?? "md",
      launcher_icon: w.launcher_icon ?? "chat",
      launcher_icon_url: w.launcher_icon_url ?? undefined,
      show_avatar_in_messages: w.show_avatar_in_messages ?? true,
      branding_text: w.branding_text ?? undefined,
    },
    document_filter: bot.document_filter,
  };
}

export function BotForm({ mode, bot }: Props) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const form = useForm<CreateBotFormData>({
    // The Zod resolver's inferred output type can drift from the input
    // type (literal-default + transform pairs widen it). Cast to the
    // concrete form-data type so Controller / handleSubmit see a
    // single, stable shape.
    resolver: zodResolver(createBotSchema) as Resolver<CreateBotFormData>,
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
  const widgetWatch = useWatch({
    control: form.control,
    name: "widget_config",
  });
  const watched = useWatch({ control: form.control });

  // Single-step undo for preset application.
  const previousWidget = useRef<CreateBotFormData["widget_config"] | null>(null);
  const [canUndoPreset, setCanUndoPreset] = useState(false);

  function applyPreset(preset: ThemePreset) {
    previousWidget.current = form.getValues("widget_config");
    const merged = {
      ...form.getValues("widget_config"),
      ...preset.apply,
    } as CreateBotFormData["widget_config"];
    form.setValue("widget_config", merged, { shouldDirty: true, shouldTouch: true });
    setCanUndoPreset(true);
  }

  function undoPreset() {
    if (!previousWidget.current) return;
    form.setValue("widget_config", previousWidget.current, {
      shouldDirty: true,
      shouldTouch: true,
    });
    previousWidget.current = null;
    setCanUndoPreset(false);
  }

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

  const previewBotId = bot?.id ?? "new";
  const themeForWarnings = {
    primary_color: widgetWatch?.primary_color,
    primary_foreground: widgetWatch?.primary_foreground ?? null,
    background: widgetWatch?.background ?? null,
    foreground: widgetWatch?.foreground ?? null,
    font_family: widgetWatch?.font_family,
    display_font: widgetWatch?.display_font ?? null,
    radius: widgetWatch?.radius,
    launcher_icon: widgetWatch?.launcher_icon,
    tone: watched.tone,
    branding_text: widgetWatch?.branding_text ?? null,
  };

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,420px)]">
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8" noValidate>
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
                {...form.register("model_config.temperature", { valueAsNumber: true })}
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
                {...form.register("model_config.max_tokens", { valueAsNumber: true })}
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
                    <SelectItem value="all">All documents in the workspace</SelectItem>
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
            <h2 className="text-base font-medium">Theme</h2>
            <p className="text-sm text-muted-foreground">
              Make the widget look like yours — start from a preset, then fine-tune.
            </p>
          </header>
          <PresetRow
            onApply={applyPreset}
            onUndo={undoPreset}
            canUndo={canUndoPreset}
          />
        </section>

        <section className="space-y-4 rounded-xl border border-border/60 bg-card p-5">
          <header className="space-y-1">
            <h2 className="text-base font-medium">Color</h2>
            <p className="text-sm text-muted-foreground">
              Choose the brand color and (optionally) override surface tokens.
            </p>
          </header>
          <Controller
            control={form.control}
            name="widget_config.color_mode"
            render={({ field }) => (
              <div className="grid gap-1.5 sm:max-w-[260px]">
                <Label htmlFor="bot-color-mode">Color mode</Label>
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id="bot-color-mode">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {colorModes.map((m) => (
                      <SelectItem key={m} value={m}>
                        {COLOR_MODE_LABELS[m]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <ColorField name="widget_config.primary_color" label="Primary" form={form} />
            <ColorField
              name="widget_config.primary_foreground"
              label="Text on primary"
              form={form}
              optional
              placeholder="#ffffff"
            />
            <ColorField
              name="widget_config.background"
              label="Panel background"
              form={form}
              optional
            />
            <ColorField
              name="widget_config.surface"
              label="Inputs / sources"
              form={form}
              optional
            />
            <ColorField
              name="widget_config.foreground"
              label="Body text"
              form={form}
              optional
            />
            <ColorField
              name="widget_config.muted"
              label="Secondary text"
              form={form}
              optional
            />
            <ColorField
              name="widget_config.border"
              label="Borders"
              form={form}
              optional
            />
          </div>
          <ContrastBadge
            primary={widgetWatch?.primary_color}
            primaryFg={widgetWatch?.primary_foreground ?? null}
          />
          <AntiSlopAside theme={themeForWarnings} section="color" />
        </section>

        <section className="space-y-4 rounded-xl border border-border/60 bg-card p-5">
          <header className="space-y-1">
            <h2 className="text-base font-medium">Typography</h2>
            <p className="text-sm text-muted-foreground">
              Pick a body font, optionally pair it with a display font for headings.
            </p>
          </header>
          <div className="grid gap-4 sm:grid-cols-2">
            <Controller
              control={form.control}
              name="widget_config.font_family"
              render={({ field }) => (
                <div className="grid gap-1.5">
                  <Label htmlFor="bot-font-body">Body font</Label>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="bot-font-body">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {WIDGET_FONT_KEYS.map((k) => (
                        <SelectItem key={k} value={k}>
                          {WIDGET_FONTS[k].label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FontSample fontKey={field.value} />
                </div>
              )}
            />
            <Controller
              control={form.control}
              name="widget_config.display_font"
              render={({ field }) => (
                <div className="grid gap-1.5">
                  <Label htmlFor="bot-font-display">
                    Display font (header) — optional
                  </Label>
                  <Select
                    value={field.value ?? "__none"}
                    onValueChange={(v) => field.onChange(v === "__none" ? undefined : v)}
                  >
                    <SelectTrigger id="bot-font-display">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__none">Same as body</SelectItem>
                      {WIDGET_FONT_KEYS.map((k) => (
                        <SelectItem key={k} value={k}>
                          {WIDGET_FONTS[k].label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {field.value && <FontSample fontKey={field.value} />}
                </div>
              )}
            />
            <Controller
              control={form.control}
              name="widget_config.base_font_size"
              render={({ field }) => (
                <div className="grid gap-1.5">
                  <Label htmlFor="bot-font-size">Base font size</Label>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="bot-font-size">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {sizeTokens.map((s) => (
                        <SelectItem key={s} value={s}>
                          {SIZE_LABELS[s]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            />
          </div>
          <AntiSlopAside theme={themeForWarnings} section="typography" />
        </section>

        <section className="space-y-4 rounded-xl border border-border/60 bg-card p-5">
          <header className="space-y-1">
            <h2 className="text-base font-medium">Shape &amp; density</h2>
            <p className="text-sm text-muted-foreground">
              Corner radius, spacing, and the launcher button shape.
            </p>
          </header>
          <div className="grid gap-4 sm:grid-cols-3">
            <SelectField
              control={form.control}
              name="widget_config.radius"
              label="Corner radius"
              options={radiusTokens}
              labels={RADIUS_LABELS}
            />
            <SelectField
              control={form.control}
              name="widget_config.density"
              label="Density"
              options={densityTokens}
              labels={DENSITY_LABELS}
            />
            <SelectField
              control={form.control}
              name="widget_config.position"
              label="Position"
              options={botPositions}
              labels={POSITION_LABELS}
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <SelectField
              control={form.control}
              name="widget_config.launcher_shape"
              label="Launcher shape"
              options={launcherShapes}
              labels={LAUNCHER_SHAPE_LABELS}
            />
            <SelectField
              control={form.control}
              name="widget_config.launcher_size"
              label="Launcher size"
              options={sizeTokens}
              labels={SIZE_LABELS}
            />
            <SelectField
              control={form.control}
              name="widget_config.panel_size"
              label="Panel size"
              options={sizeTokens}
              labels={SIZE_LABELS}
            />
          </div>
        </section>

        <section className="space-y-4 rounded-xl border border-border/60 bg-card p-5">
          <header className="space-y-1">
            <h2 className="text-base font-medium">Branding</h2>
            <p className="text-sm text-muted-foreground">
              Avatar, launcher glyph, and footer credit.
            </p>
          </header>
          <div className="grid gap-4 sm:grid-cols-2">
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
            <SelectField
              control={form.control}
              name="widget_config.launcher_icon"
              label="Launcher icon"
              options={launcherIcons}
              labels={LAUNCHER_ICON_LABELS}
            />
          </div>
          {widgetWatch?.launcher_icon === "custom" && (
            <div className="grid gap-1.5">
              <Label htmlFor="bot-launcher-url">Launcher icon URL (https)</Label>
              <Input
                id="bot-launcher-url"
                type="url"
                placeholder="https://…"
                {...form.register("widget_config.launcher_icon_url")}
              />
              {form.formState.errors.widget_config?.launcher_icon_url && (
                <p className="text-xs text-destructive" role="alert">
                  {form.formState.errors.widget_config.launcher_icon_url.message}
                </p>
              )}
            </div>
          )}
          <Controller
            control={form.control}
            name="widget_config.show_avatar_in_messages"
            render={({ field }) => (
              <Label
                htmlFor="bot-avatar-msgs"
                className="flex cursor-pointer items-start gap-2.5 rounded-lg border border-border/60 bg-muted/20 px-3 py-2 transition-colors has-aria-checked:border-foreground/30 has-aria-checked:bg-muted/60"
              >
                <Checkbox
                  id="bot-avatar-msgs"
                  checked={field.value}
                  onCheckedChange={(v) => field.onChange(Boolean(v))}
                />
                <span className="grid gap-0.5 text-sm leading-tight">
                  <span className="font-medium">Show avatar next to assistant messages</span>
                  <span className="text-xs text-muted-foreground">
                    Falls back to the bot name initial when no avatar URL is set.
                  </span>
                </span>
              </Label>
            )}
          />
          <div className="grid gap-1.5">
            <Label htmlFor="bot-branding-text">
              Footer branding text — paid plans only
            </Label>
            <Input
              id="bot-branding-text"
              placeholder="Powered by Acme"
              maxLength={80}
              {...form.register("widget_config.branding_text")}
            />
            <p className="text-xs text-muted-foreground">
              Replaces &ldquo;Powered by MongoRAG&rdquo;. Free-tier saves are
              rejected by the server with a clear error.
            </p>
            {form.formState.errors.widget_config?.branding_text && (
              <p className="text-xs text-destructive" role="alert">
                {form.formState.errors.widget_config.branding_text.message}
              </p>
            )}
          </div>
          <AntiSlopAside theme={themeForWarnings} section="identity" />
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

      <div className="lg:sticky lg:top-6 lg:self-start">
        <PreviewPane
          botId={previewBotId}
          draft={{
            name: watched.name ?? "Assistant",
            welcome_message: watched.welcome_message ?? "",
            widget_config:
              (watched.widget_config as CreateBotFormData["widget_config"]) ??
              defaultBotFormValues.widget_config,
          }}
        />
      </div>
    </div>
  );
}

interface ColorFieldProps {
  name: FieldPath<CreateBotFormData>;
  label: string;
  form: UseFormReturn<CreateBotFormData>;
  optional?: boolean;
  placeholder?: string;
}

function ColorField({ name, label, form, optional, placeholder }: ColorFieldProps) {
  const value = form.watch(name) ?? "";
  const id = `field-${name.replace(/\./g, "-")}`;
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={id}>
        {label}
        {optional && <span className="text-muted-foreground"> (optional)</span>}
      </Label>
      <div className="flex items-center gap-2">
        <input
          id={id}
          type="color"
          value={typeof value === "string" && /^#[0-9a-fA-F]{6}$/.test(value) ? value : "#0f172a"}
          onChange={(e) => form.setValue(name, e.target.value, { shouldDirty: true })}
          className="h-9 w-12 cursor-pointer rounded border border-border/60 bg-background"
          aria-label={`${label} swatch`}
        />
        <Input
          {...form.register(name)}
          placeholder={placeholder ?? "#RRGGBB"}
          className="font-mono text-sm"
        />
      </div>
    </div>
  );
}

interface SelectFieldProps {
  control: Control<CreateBotFormData>;
  name: FieldPath<CreateBotFormData>;
  label: string;
  options: readonly string[];
  labels: Record<string, string>;
}

function SelectField({ control, name, label, options, labels }: SelectFieldProps) {
  const id = `select-${name.replace(/\./g, "-")}`;
  return (
    <Controller
      control={control}
      name={name}
      render={({ field }) => (
        <div className="grid gap-1.5">
          <Label htmlFor={id}>{label}</Label>
          <Select value={String(field.value ?? "")} onValueChange={field.onChange}>
            <SelectTrigger id={id}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {options.map((opt) => (
                <SelectItem key={opt} value={opt}>
                  {labels[opt] ?? opt}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}
    />
  );
}

function FontSample({ fontKey }: { fontKey: string }) {
  const stack = WIDGET_FONTS[fontKey as keyof typeof WIDGET_FONTS]?.stack ?? "system-ui";
  return (
    <div
      className="rounded border border-border/60 bg-muted/30 px-3 py-2 text-sm"
      style={{ fontFamily: stack }}
    >
      <div className="text-base font-semibold">Aa Bb Cc</div>
      <div className="text-muted-foreground">The quick brown fox jumps over the lazy dog.</div>
    </div>
  );
}

function ContrastBadge({
  primary,
  primaryFg,
}: {
  primary: string | undefined;
  primaryFg: string | null | undefined;
}) {
  if (!primary || !primaryFg) return null;
  const ratio = contrastRatio(primary, primaryFg);
  if (ratio === null) return null;
  const grade = wcagGrade(ratio);
  const color =
    grade === "fail"
      ? "text-destructive"
      : grade === "AA-large"
        ? "text-amber-600"
        : "text-emerald-600";
  return (
    <p className={`text-xs ${color}`}>
      Contrast {ratio.toFixed(2)}:1 — WCAG <strong>{grade}</strong>
      {grade === "fail" && " — text on primary may be unreadable"}
    </p>
  );
}
