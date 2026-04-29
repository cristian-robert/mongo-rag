import { describe, expect, it } from "vitest";

import { CHECKOUT_PLAN_TIERS, checkoutInputSchema } from "./billing";

describe("checkoutInputSchema", () => {
  it("accepts pro + standard", () => {
    const result = checkoutInputSchema.safeParse({
      plan: "pro",
      model_tier: "standard",
    });
    expect(result.success).toBe(true);
  });

  it("accepts enterprise + ultra", () => {
    const result = checkoutInputSchema.safeParse({
      plan: "enterprise",
      model_tier: "ultra",
    });
    expect(result.success).toBe(true);
  });

  it("rejects free as a checkout plan", () => {
    const result = checkoutInputSchema.safeParse({
      plan: "free",
      model_tier: "starter",
    });
    expect(result.success).toBe(false);
  });

  it("rejects starter as a checkout plan", () => {
    // starter is a tenant plan but not purchaseable via Checkout.
    const result = checkoutInputSchema.safeParse({
      plan: "starter",
      model_tier: "standard",
    });
    expect(result.success).toBe(false);
  });

  it("rejects unknown model tiers", () => {
    const result = checkoutInputSchema.safeParse({
      plan: "pro",
      model_tier: "infinite",
    });
    expect(result.success).toBe(false);
  });

  it("only purchaseable plans appear in CHECKOUT_PLAN_TIERS", () => {
    expect(CHECKOUT_PLAN_TIERS).toEqual(["pro", "enterprise"]);
  });
});
