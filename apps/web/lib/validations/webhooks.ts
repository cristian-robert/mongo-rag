import { z } from "zod/v3";

export const webhookEvents = [
  "document.ingested",
  "document.deleted",
  "chat.completed",
  "subscription.updated",
] as const;

export type WebhookEventValue = (typeof webhookEvents)[number];

export const createWebhookSchema = z.object({
  url: z
    .string()
    .trim()
    .min(1, "URL is required")
    .max(2048, "URL must be at most 2048 characters")
    .url("Must be a valid URL")
    .refine(
      (v) => v.startsWith("https://") || v.startsWith("http://"),
      "URL must use http(s)",
    ),
  events: z
    .array(z.enum(webhookEvents))
    .min(1, "Select at least one event"),
  description: z
    .string()
    .trim()
    .max(200, "Description must be at most 200 characters")
    .optional()
    .or(z.literal("")),
  active: z.boolean(),
});

export type CreateWebhookFormData = z.infer<typeof createWebhookSchema>;
