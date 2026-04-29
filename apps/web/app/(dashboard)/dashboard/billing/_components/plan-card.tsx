"use client";

import { useState } from "react";
import { Check } from "lucide-react";

import { cn } from "@/lib/utils";
import type { ModelTier, PlanInfo, PlanTier } from "@/lib/billing";

import { UpgradeButton } from "./upgrade-button";

type PriceMap = Partial<Record<ModelTier, number>>;

type Props = {
  plan: PlanInfo;
  prices: PriceMap;
  modelTiers: ModelTier[];
  modelLabels: Record<ModelTier, string>;
  current: boolean;
  highlight?: boolean;
  description: string;
};

const numberFmt = new Intl.NumberFormat("en-US");

const PLAN_LABELS: Record<PlanTier, string> = {
  free: "Free",
  starter: "Starter",
  pro: "Pro",
  enterprise: "Enterprise",
};

function formatPrice(cents: number | undefined): string {
  if (typeof cents !== "number") return "—";
  const dollars = cents / 100;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: dollars % 1 === 0 ? 0 : 2,
    maximumFractionDigits: 2,
  }).format(dollars);
}

export function PlanCard({
  plan,
  prices,
  modelTiers,
  modelLabels,
  current,
  highlight = false,
  description,
}: Props) {
  const tiersWithPrice = modelTiers.filter((t) => typeof prices[t] === "number");
  const initial = tiersWithPrice[0] ?? "standard";
  const [selectedTier, setSelectedTier] = useState<ModelTier>(initial);

  const purchaseable = plan.plan === "pro" || plan.plan === "enterprise";
  const price = prices[selectedTier];

  return (
    <article
      className={cn(
        "relative flex h-full flex-col gap-4 rounded-xl border bg-card p-5 text-card-foreground",
        highlight
          ? "border-foreground/40 ring-1 ring-foreground/15"
          : "border-border",
      )}
    >
      {highlight ? (
        <span className="absolute -top-2 right-4 rounded-full bg-foreground px-2 py-0.5 font-mono text-[0.65rem] uppercase tracking-[0.18em] text-background">
          Recommended
        </span>
      ) : null}

      <header className="flex flex-col gap-1">
        <h3 className="font-heading text-lg font-semibold tracking-tight">
          {PLAN_LABELS[plan.plan]}
        </h3>
        <p className="text-[0.78rem] text-muted-foreground">{description}</p>
      </header>

      <div className="flex items-baseline gap-1">
        <span className="font-heading text-3xl font-semibold tabular-nums">
          {purchaseable ? formatPrice(price) : "Free"}
        </span>
        {purchaseable ? (
          <span className="text-[0.78rem] text-muted-foreground">/ month</span>
        ) : null}
      </div>

      {purchaseable && tiersWithPrice.length > 0 ? (
        <fieldset className="flex flex-col gap-1.5">
          <legend className="text-[0.7rem] font-medium uppercase tracking-wide text-muted-foreground">
            Model tier
          </legend>
          <div
            role="radiogroup"
            aria-label="Model tier"
            className="grid grid-cols-2 gap-1.5"
          >
            {tiersWithPrice.map((tier) => {
              const active = selectedTier === tier;
              return (
                <button
                  key={tier}
                  type="button"
                  role="radio"
                  aria-checked={active}
                  onClick={() => setSelectedTier(tier)}
                  className={cn(
                    "rounded-md border px-2.5 py-1.5 text-left text-[0.78rem] transition-colors",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    active
                      ? "border-foreground/40 bg-foreground/5 text-foreground"
                      : "border-border bg-background text-muted-foreground hover:border-foreground/20 hover:text-foreground",
                  )}
                >
                  <span className="block font-medium capitalize">
                    {modelLabels[tier] ?? tier}
                  </span>
                  <span className="block font-mono text-[0.7rem] tabular-nums text-muted-foreground">
                    {formatPrice(prices[tier])}
                  </span>
                </button>
              );
            })}
          </div>
        </fieldset>
      ) : null}

      <ul className="flex flex-col gap-1.5 border-t border-border pt-4 text-[0.82rem]">
        <Feature text={`${numberFmt.format(plan.limits.queries_per_month)} queries / month`} />
        <Feature text={`${numberFmt.format(plan.limits.documents)} documents`} />
        <Feature text={`${numberFmt.format(plan.limits.bots)} bots`} />
      </ul>

      <div className="mt-auto pt-2">
        {current ? (
          <span className="block w-full rounded-md border border-border bg-muted/40 px-3 py-2 text-center text-[0.8rem] font-medium text-muted-foreground">
            Current plan
          </span>
        ) : purchaseable ? (
          <UpgradeButton
            plan={plan.plan}
            modelTier={selectedTier}
            label={`Upgrade to ${PLAN_LABELS[plan.plan]}`}
            variant={highlight ? "default" : "outline"}
            className="w-full"
          />
        ) : (
          <span className="block w-full rounded-md border border-border bg-muted/40 px-3 py-2 text-center text-[0.8rem] font-medium text-muted-foreground">
            Default tier
          </span>
        )}
      </div>
    </article>
  );
}

function Feature({ text }: { text: string }) {
  return (
    <li className="flex items-start gap-2 text-foreground">
      <Check
        className="mt-0.5 size-3.5 text-foreground/70"
        aria-hidden="true"
      />
      <span>{text}</span>
    </li>
  );
}
