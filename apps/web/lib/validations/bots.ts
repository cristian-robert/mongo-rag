import { z } from "zod/v3";

export const botTones = [
  "professional",
  "friendly",
  "concise",
  "technical",
  "playful",
] as const;

export const botPositions = ["bottom-right", "bottom-left"] as const;

export const documentFilterModes = ["all", "ids"] as const;

const slugRegex = /^[a-z0-9](?:[a-z0-9-]{1,48}[a-z0-9])?$/;

const slugSchema = z
  .string()
  .trim()
  .toLowerCase()
  .regex(
    slugRegex,
    "Lowercase a-z, 0-9 and hyphens only; 2-50 chars; cannot start or end with -",
  );

const widgetConfigSchema = z.object({
  primary_color: z
    .string()
    .regex(/^#[0-9a-fA-F]{6}$/, "Use a #RRGGBB hex color"),
  position: z.enum(botPositions),
  avatar_url: z
    .string()
    .url("Must be a valid URL")
    .startsWith("https://", "URL must use https://")
    .max(500)
    .optional()
    .or(z.literal("").transform(() => undefined)),
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
  },
  document_filter: { mode: "all", document_ids: [] },
};
