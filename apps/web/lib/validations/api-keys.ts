import { z } from "zod/v3";

export const apiKeyPermissions = ["chat", "search"] as const;

export const createApiKeySchema = z.object({
  name: z
    .string()
    .min(2, "Name must be at least 2 characters")
    .max(100, "Name must be at most 100 characters")
    .trim(),
  permissions: z
    .array(z.enum(apiKeyPermissions))
    .min(1, "Select at least one permission"),
});

export type CreateApiKeyFormData = z.infer<typeof createApiKeySchema>;
