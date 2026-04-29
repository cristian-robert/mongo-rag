import type { Metadata } from "next";

import { ApiError } from "@/lib/api-client";
import {
  getPlans,
  getUsage,
  type ModelTier,
  type PlanInfo,
  type PlansResponse,
  type UsageResponse,
} from "@/lib/billing";

import { CheckoutStatusBanner } from "./_components/checkout-status-banner";
import { CurrentPlanCard } from "./_components/current-plan-card";
import { PlanCard } from "./_components/plan-card";
import { UsagePanel } from "./_components/usage-panel";

export const metadata: Metadata = {
  title: "Billing — MongoRAG",
  description:
    "View your current plan, monthly usage, and upgrade your MongoRAG subscription.",
};

// JWT minted server-side per request, never cache.
export const dynamic = "force-dynamic";

const MODEL_TIER_ORDER: ModelTier[] = ["starter", "standard", "premium", "ultra"];
const MODEL_TIER_LABELS: Record<ModelTier, string> = {
  starter: "Starter",
  standard: "Standard",
  premium: "Premium",
  ultra: "Ultra",
};

type LoadResult = {
  plans: PlansResponse | null;
  usage: UsageResponse | null;
  plansError: string | null;
  usageError: string | null;
};

async function loadBillingData(): Promise<LoadResult> {
  const [plansResult, usageResult] = await Promise.allSettled([
    getPlans(),
    getUsage(),
  ]);
  const plans = plansResult.status === "fulfilled" ? plansResult.value : null;
  const usage = usageResult.status === "fulfilled" ? usageResult.value : null;

  const plansError =
    plansResult.status === "rejected"
      ? plansResult.reason instanceof ApiError
        ? plansResult.reason.message
        : "Could not load pricing right now."
      : null;
  const usageError =
    usageResult.status === "rejected"
      ? usageResult.reason instanceof ApiError
        ? usageResult.reason.message
        : "Could not load usage data right now."
      : null;

  return { plans, usage, plansError, usageError };
}

function buildPriceMap(
  modelTiers: PlansResponse["model_tiers"],
  plan: "pro" | "enterprise",
): Partial<Record<ModelTier, number>> {
  const map: Partial<Record<ModelTier, number>> = {};
  for (const t of modelTiers) {
    const cents = plan === "pro" ? t.pro_price_cents : t.enterprise_price_cents;
    if (typeof cents === "number") {
      map[t.tier] = cents;
    }
  }
  return map;
}

function findPlan(plans: PlanInfo[], target: PlanInfo["plan"]): PlanInfo | undefined {
  return plans.find((p) => p.plan === target);
}

export default async function BillingPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const rawStatus = Array.isArray(params.status) ? params.status[0] : params.status;
  const checkoutStatus =
    rawStatus === "success" || rawStatus === "cancelled" ? rawStatus : null;

  const { plans, usage, plansError, usageError } = await loadBillingData();
  const currentPlan = usage?.plan ?? "free";

  const free = plans ? findPlan(plans.plans, "free") : undefined;
  const pro = plans ? findPlan(plans.plans, "pro") : undefined;
  const enterprise = plans ? findPlan(plans.plans, "enterprise") : undefined;

  const proPrices = plans ? buildPriceMap(plans.model_tiers, "pro") : {};
  const enterprisePrices = plans
    ? buildPriceMap(plans.model_tiers, "enterprise")
    : {};

  return (
    <div className="mx-auto w-full max-w-5xl space-y-8 px-2 py-2">
      <header className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-1">
          <p className="font-mono text-[0.7rem] tracking-[0.2em] text-muted-foreground uppercase">
            Plans &amp; usage
          </p>
          <h1 className="font-heading text-2xl leading-tight font-medium tracking-tight">
            Billing
          </h1>
          <p className="max-w-xl text-sm text-muted-foreground">
            Track your monthly usage against plan limits and upgrade when you
            need more headroom. Payments and cancellations are handled by
            Stripe.
          </p>
        </div>
      </header>

      {checkoutStatus ? <CheckoutStatusBanner status={checkoutStatus} /> : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <CurrentPlanCard usage={usage} loadError={usageError} />
        <UsagePanel usage={usage} loadError={usageError} />
      </div>

      <section
        aria-labelledby="plans-heading"
        className="flex flex-col gap-4"
      >
        <div className="flex flex-col gap-1">
          <h2
            id="plans-heading"
            className="font-heading text-base font-medium tracking-tight"
          >
            Compare plans
          </h2>
          <p className="text-[0.82rem] text-muted-foreground">
            Pick the plan and model tier that fits your workload. You can
            change tiers any time from this page.
          </p>
        </div>

        {plansError ? (
          <p
            role="alert"
            className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-[0.82rem] text-destructive"
          >
            {plansError}
          </p>
        ) : plans && free && pro && enterprise ? (
          <div className="grid gap-4 md:grid-cols-3">
            <PlanCard
              plan={free}
              prices={{}}
              modelTiers={MODEL_TIER_ORDER}
              modelLabels={MODEL_TIER_LABELS}
              current={currentPlan === "free"}
              description="Try MongoRAG with light usage and a single bot."
            />
            <PlanCard
              plan={pro}
              prices={proPrices}
              modelTiers={MODEL_TIER_ORDER}
              modelLabels={MODEL_TIER_LABELS}
              current={currentPlan === "pro"}
              highlight
              description="For growing teams shipping production assistants."
            />
            <PlanCard
              plan={enterprise}
              prices={enterprisePrices}
              modelTiers={MODEL_TIER_ORDER}
              modelLabels={MODEL_TIER_LABELS}
              current={currentPlan === "enterprise"}
              description="High volume, premium models, and white-glove support."
            />
          </div>
        ) : (
          <p className="rounded-md border border-border bg-muted/40 px-3 py-2 text-[0.82rem] text-muted-foreground">
            Pricing is unavailable right now.
          </p>
        )}
      </section>

      <section
        aria-labelledby="billing-mgmt-heading"
        className="flex flex-col gap-2 rounded-xl border border-dashed border-border bg-muted/20 p-5"
      >
        <h2
          id="billing-mgmt-heading"
          className="font-heading text-base font-medium tracking-tight"
        >
          Manage billing
        </h2>
        <p className="text-[0.82rem] text-muted-foreground">
          To update your payment method, download invoices, or cancel your
          subscription, contact{" "}
          <a
            href="mailto:billing@mongorag.com"
            className="text-foreground underline-offset-4 hover:underline"
          >
            billing@mongorag.com
          </a>
          . Self-service customer portal is coming soon.
        </p>
      </section>
    </div>
  );
}
