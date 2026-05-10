import { z } from "zod/v3";

import { WIDGET_FONT_KEYS } from "@/lib/widget-fonts";

export const botTones = [
  "professional",
  "friendly",
  "concise",
  "technical",
  "playful",
] as const;

export const botPositions = ["bottom-right", "bottom-left"] as const;

export const documentFilterModes = ["all", "ids"] as const;

export const colorModes = ["light", "dark", "auto"] as const;
export const radiusTokens = ["none", "sm", "md", "lg", "full"] as const;
export const densityTokens = ["compact", "comfortable", "spacious"] as const;
export const sizeTokens = ["sm", "md", "lg"] as const;
export const launcherShapes = ["circle", "rounded-square", "pill"] as const;
export const launcherIcons = ["chat", "sparkle", "book", "question", "custom"] as const;

const slugRegex = /^[a-z0-9](?:[a-z0-9-]{1,48}[a-z0-9])?$/;

const slugSchema = z
  .string()
  .trim()
  .toLowerCase()
  .regex(
    slugRegex,
    "Lowercase a-z, 0-9 and hyphens only; 2-50 chars; cannot start or end with -",
  );

// Hex color (RGB or RGBA). Mirrors apps/api/src/models/bot.py _HEX_COLOR_PATTERN.
const hexColorSchema = z
  .string()
  .regex(/^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$/, "Use a #RRGGBB or #RRGGBBAA hex color");

const optionalHexColorSchema = hexColorSchema.optional().or(z.literal("").transform(() => undefined));

const httpsUrlSchema = z
  .string()
  .url("Must be a valid URL")
  .startsWith("https://", "URL must use https://")
  .max(500);

const optionalHttpsUrl = httpsUrlSchema.optional().or(z.literal("").transform(() => undefined));

const darkOverridesSchema = z
  .object({
    background: optionalHexColorSchema,
    surface: optionalHexColorSchema,
    foreground: optionalHexColorSchema,
    muted: optionalHexColorSchema,
    border: optionalHexColorSchema,
    primary: optionalHexColorSchema,
    primary_foreground: optionalHexColorSchema,
  })
  .partial()
  .optional();

const widgetConfigSchema = z
  .object({
    // Existing
    primary_color: hexColorSchema,
    position: z.enum(botPositions),
    avatar_url: optionalHttpsUrl,
    // New: color tokens
    color_mode: z.enum(colorModes).default("light"),
    background: optionalHexColorSchema,
    surface: optionalHexColorSchema,
    foreground: optionalHexColorSchema,
    muted: optionalHexColorSchema,
    border: optionalHexColorSchema,
    primary_foreground: optionalHexColorSchema,
    dark_overrides: darkOverridesSchema,
    // Typography
    font_family: z.enum(WIDGET_FONT_KEYS).default("system"),
    display_font: z.enum(WIDGET_FONT_KEYS).optional(),
    base_font_size: z.enum(sizeTokens).default("md"),
    // Shape & density
    radius: z.enum(radiusTokens).default("md"),
    density: z.enum(densityTokens).default("comfortable"),
    launcher_shape: z.enum(launcherShapes).default("circle"),
    launcher_size: z.enum(sizeTokens).default("md"),
    panel_size: z.enum(sizeTokens).default("md"),
    // Branding & icons
    launcher_icon: z.enum(launcherIcons).default("chat"),
    launcher_icon_url: optionalHttpsUrl,
    show_avatar_in_messages: z.boolean().default(true),
    branding_text: z
      .string()
      .max(80)
      .optional()
      .or(z.literal("").transform(() => undefined)),
  })
  .superRefine((cfg, ctx) => {
    if (cfg.launcher_icon === "custom" && !cfg.launcher_icon_url) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["launcher_icon_url"],
        message: "Required when launcher_icon is 'custom'",
      });
    }
  });

const modelConfigSchema = z.object({
  temperature: z.number().min(0).max(1),
  max_tokens: z.number().int().min(64).max(8192),
});

const documentFilterSchema = z.object({
  mode: z.enum(documentFilterModes),
  document_ids: z.array(z.string().min(1)).max(200),
});

export const createBotSchema = z.object({
  name: z.string().trim().min(2, "Name is required").max(80),
  slug: slugSchema,
  description: z.string().trim().max(280).optional().or(z.literal("")),
  system_prompt: z
    .string()
    .trim()
    .min(10, "Add at least a sentence of instructions")
    .max(4000),
  welcome_message: z
    .string()
    .trim()
    .min(1, "Welcome message is required")
    .max(500),
  tone: z.enum(botTones),
  is_public: z.boolean(),
  model_config: modelConfigSchema,
  widget_config: widgetConfigSchema,
  document_filter: documentFilterSchema,
});

export const updateBotSchema = createBotSchema.partial().omit({ slug: true });

export type CreateBotFormData = z.infer<typeof createBotSchema>;
export type UpdateBotFormData = z.infer<typeof updateBotSchema>;

export const defaultBotFormValues: CreateBotFormData = {
  name: "",
  slug: "",
  description: "",
  system_prompt:
    "You are a helpful assistant. Answer questions using the provided knowledge base. " +
    "If the answer isn't in the knowledge base, say so honestly.",
  welcome_message: "Hi! How can I help you today?",
  tone: "professional",
  is_public: false,
  model_config: { temperature: 0.2, max_tokens: 1024 },
  widget_config: {
    primary_color: "#0f172a",
    position: "bottom-right",
    avatar_url: undefined,
    color_mode: "light",
    background: undefined,
    surface: undefined,
    foreground: undefined,
    muted: undefined,
    border: undefined,
    primary_foreground: "#ffffff",
    dark_overrides: undefined,
    font_family: "system",
    display_font: undefined,
    base_font_size: "md",
    radius: "md",
    density: "comfortable",
    launcher_shape: "circle",
    launcher_size: "md",
    panel_size: "md",
    launcher_icon: "chat",
    launcher_icon_url: undefined,
    show_avatar_in_messages: true,
    branding_text: undefined,
  },
  document_filter: { mode: "all", document_ids: [] },
};
