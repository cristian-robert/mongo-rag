"use server";

import { ApiError } from "@/lib/api-client";
import { createCheckoutSession } from "@/lib/billing";
import { checkoutInputSchema } from "@/lib/validations/billing";

export type StartCheckoutResult =
  | { ok: true; checkout_url: string }
  | { ok: false; error: string };

/**
 * Build redirect URLs from the server-controlled NEXT_PUBLIC_APP_URL so a malicious
 * client cannot make Stripe redirect to an attacker-controlled domain.
 */
function buildRedirectUrls(): { success_url: string; cancel_url: string } {
  const origin = process.env.NEXT_PUBLIC_APP_URL;
  if (!origin) {
    throw new Error("NEXT_PUBLIC_APP_URL is not configured");
  }
  // Trim trailing slashes for predictable concatenation.
  const base = origin.replace(/\/+$/, "");
  return {
    success_url: `${base}/dashboard/billing?status=success&session_id={CHECKOUT_SESSION_ID}`,
    cancel_url: `${base}/dashboard/billing?status=cancelled`,
  };
}

export async function startCheckoutAction(
  input: unknown,
): Promise<StartCheckoutResult> {
  const parsed = checkoutInputSchema.safeParse(input);
  if (!parsed.success) {
    return {
      ok: false,
      error: parsed.error.issues[0]?.message ?? "Invalid input",
    };
  }

  let urls: { success_url: string; cancel_url: string };
  try {
    urls = buildRedirectUrls();
  } catch {
    return {
      ok: false,
      error: "Checkout is not configured. Please contact support.",
    };
  }

  try {
    const session = await createCheckoutSession({
      plan: parsed.data.plan,
      model_tier: parsed.data.model_tier,
      success_url: urls.success_url,
      cancel_url: urls.cancel_url,
    });
    return { ok: true, checkout_url: session.checkout_url };
  } catch (err) {
    if (err instanceof ApiError) {
      // 503 = Stripe not configured. Surface a friendlier message.
      if (err.status === 503) {
        return {
          ok: false,
          error: "Billing is temporarily unavailable. Please try again later.",
        };
      }
      return { ok: false, error: err.message };
    }
    return { ok: false, error: "Could not start checkout. Please try again." };
  }
}
