/**
 * Server-side fetch of the public pricing catalog. Unauthenticated — the
 * `/api/v1/billing/plans` endpoint is intentionally public per #10.
 */

import "server-only";

import type { PlansResponse } from "@/lib/billing";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8100";

const FALLBACK: PlansResponse = {
  plans: [
    {
      plan: "free",
      limits: { queries_per_month: 100, documents: 50, bots: 1 },
    },
    {
      plan: "pro",
      limits: { queries_per_month: 10_000, documents: 1_000, bots: 10 },
    },
    {
      plan: "enterprise",
      limits: { queries_per_month: 1_000_000, documents: 100_000, bots: 1_000 },
    },
  ],
  model_tiers: [
    {
      tier: "starter",
      pro_price_cents: 0,
      enterprise_price_cents: 0,
      models: [],
    },
    {
      tier: "standard",
      pro_price_cents: 2900,
      enterprise_price_cents: 9900,
      models: [],
    },
    {
      tier: "premium",
      pro_price_cents: 4900,
      enterprise_price_cents: 14900,
      models: [],
    },
  ],
};

export async function getPublicPlans(): Promise<PlansResponse> {
  try {
    const res = await fetch(`${API_URL}/api/v1/billing/plans`, {
      next: { revalidate: 300 },
    });
    if (!res.ok) {
      return FALLBACK;
    }
    return (await res.json()) as PlansResponse;
  } catch {
    return FALLBACK;
  }
}
