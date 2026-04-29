import { z } from "zod/v3";

export const PLAN_TIERS = ["free", "starter", "pro", "enterprise"] as const;
export const MODEL_TIERS = ["starter", "standard", "premium", "ultra"] as const;

export const CHECKOUT_PLAN_TIERS = ["pro", "enterprise"] as const;

export const checkoutInputSchema = z.object({
  plan: z.enum(CHECKOUT_PLAN_TIERS, {
    errorMap: () => ({ message: "Plan must be 'pro' or 'enterprise'" }),
  }),
  model_tier: z.enum(MODEL_TIERS, {
    errorMap: () => ({ message: "Invalid model tier" }),
  }),
});

export type CheckoutInput = z.infer<typeof checkoutInputSchema>;
