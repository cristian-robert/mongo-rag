import type { Metadata } from "next";
import Link from "next/link";
import { CheckIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { PlanInfo, PlanTier } from "@/lib/billing";
import { getPublicPlans } from "@/lib/marketing/plans";

export const metadata: Metadata = {
  title: "Pricing — MongoRAG",
  description:
    "Compare MongoRAG plans. Free for side projects, Pro for production, Enterprise for regulated workloads.",
};

interface PlanCopy {
  name: string;
  tagline: string;
  price: string;
  priceSuffix?: string;
  cta: { label: string; href: string };
  features: string[];
  highlight?: boolean;
}

const PLAN_COPY: Record<PlanTier, PlanCopy> = {
  free: {
    name: "Free",
    tagline: "Everything you need to ship a side project.",
    price: "$0",
    priceSuffix: "/forever",
    cta: { label: "Start for free", href: "/signup" },
    features: [
      "Hybrid RRF search",
      "Embeddable widget",
      "Email support",
      "Community-tier models",
    ],
  },
  starter: {
    name: "Starter",
    tagline: "For solo founders shipping their first AI feature.",
    price: "$19",
    priceSuffix: "/mo",
    cta: { label: "Choose Starter", href: "/signup?plan=starter" },
    features: [
      "Standard models (GPT-4 class)",
      "Custom branding",
      "Email support",
    ],
  },
  pro: {
    name: "Pro",
    tagline: "For SaaS teams with real customers.",
    price: "From $29",
    priceSuffix: "/mo",
    cta: { label: "Upgrade to Pro", href: "/signup?plan=pro" },
    highlight: true,
    features: [
      "Premium model tiers (Claude, GPT-4o)",
      "Multiple bots & API keys",
      "Audit logs",
      "Priority support",
    ],
  },
  enterprise: {
    name: "Enterprise",
    tagline: "For regulated workloads and large rollouts.",
    price: "Custom",
    cta: { label: "Talk to sales", href: "mailto:hello@mongorag.dev" },
    features: [
      "SSO + SCIM provisioning",
      "VPC peering & private networking",
      "Dedicated support engineer",
      "Custom DPA & SOC 2 report",
    ],
  },
};

const ORDER: PlanTier[] = ["free", "pro", "enterprise"];

function formatLimit(value: number): string {
  if (value >= 1_000_000) return "Unlimited";
  if (value >= 1_000) return `${(value / 1_000).toLocaleString()}k`;
  return value.toLocaleString();
}

function findPlan(plans: PlanInfo[], tier: PlanTier): PlanInfo | undefined {
  return plans.find((p) => p.plan === tier);
}

export default async function PricingPage() {
  const data = await getPublicPlans();

  return (
    <>
      <section className="border-b border-border/60">
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:py-20">
          <div className="mx-auto max-w-2xl space-y-4 text-center">
            <p className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
              Pricing
            </p>
            <h1 className="text-balance text-4xl font-extralight tracking-tight sm:text-5xl">
              Simple plans. Transparent caps.
            </h1>
            <p className="text-balance text-muted-foreground">
              Start free. Upgrade when you need more queries, more documents,
              or premium model access.
            </p>
          </div>

          <div className="mt-14 grid gap-6 lg:grid-cols-3">
            {ORDER.map((tier) => {
              const copy = PLAN_COPY[tier];
              const plan = findPlan(data.plans, tier);
              return (
                <article
                  key={tier}
                  className={
                    copy.highlight
                      ? "relative flex flex-col rounded-2xl border-2 border-foreground/85 bg-background p-7 shadow-sm"
                      : "relative flex flex-col rounded-2xl border border-border bg-background p-7"
                  }
                >
                  {copy.highlight ? (
                    <span className="absolute -top-3 left-7 rounded-full bg-foreground px-2.5 py-0.5 font-mono text-[0.65rem] uppercase tracking-wider text-background">
                      Most popular
                    </span>
                  ) : null}
                  <header className="space-y-1">
                    <h2 className="text-xl font-medium">{copy.name}</h2>
                    <p className="text-sm text-muted-foreground">
                      {copy.tagline}
                    </p>
                  </header>
                  <div className="mt-6 flex items-baseline gap-1">
                    <span className="text-4xl font-light tracking-tight">
                      {copy.price}
                    </span>
                    {copy.priceSuffix ? (
                      <span className="text-sm text-muted-foreground">
                        {copy.priceSuffix}
                      </span>
                    ) : null}
                  </div>

                  {plan ? (
                    <dl className="mt-6 grid grid-cols-3 gap-2 rounded-lg border border-border bg-muted/30 p-3 text-center">
                      <div>
                        <dt className="font-mono text-[0.65rem] uppercase tracking-wider text-muted-foreground">
                          Queries
                        </dt>
                        <dd className="mt-0.5 text-sm font-medium">
                          {formatLimit(plan.limits.queries_per_month)}
                          <span className="text-xs font-normal text-muted-foreground">
                            /mo
                          </span>
                        </dd>
                      </div>
                      <div>
                        <dt className="font-mono text-[0.65rem] uppercase tracking-wider text-muted-foreground">
                          Docs
                        </dt>
                        <dd className="mt-0.5 text-sm font-medium">
                          {formatLimit(plan.limits.documents)}
                        </dd>
                      </div>
                      <div>
                        <dt className="font-mono text-[0.65rem] uppercase tracking-wider text-muted-foreground">
                          Bots
                        </dt>
                        <dd className="mt-0.5 text-sm font-medium">
                          {formatLimit(plan.limits.bots)}
                        </dd>
                      </div>
                    </dl>
                  ) : null}

                  <ul className="mt-6 space-y-2.5 text-sm">
                    {copy.features.map((f) => (
                      <li key={f} className="flex items-start gap-2">
                        <CheckIcon
                          aria-hidden
                          className="mt-0.5 size-4 shrink-0 text-foreground/70"
                        />
                        <span>{f}</span>
                      </li>
                    ))}
                  </ul>

                  <div className="mt-auto pt-7">
                    <Button
                      asChild
                      variant={copy.highlight ? "default" : "outline"}
                      size="lg"
                      className="w-full"
                    >
                      <Link href={copy.cta.href}>{copy.cta.label}</Link>
                    </Button>
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <section className="border-b border-border/60 bg-muted/20">
        <div className="mx-auto max-w-4xl px-4 py-16 sm:px-6">
          <h2 className="text-2xl font-light tracking-tight">
            Frequently asked
          </h2>
          <dl className="mt-6 space-y-6 text-sm">
            <div>
              <dt className="font-medium">Can I switch plans later?</dt>
              <dd className="mt-1 text-muted-foreground">
                Yes — upgrades take effect immediately and we prorate. You can
                downgrade at the end of any billing cycle.
              </dd>
            </div>
            <div>
              <dt className="font-medium">What counts as a query?</dt>
              <dd className="mt-1 text-muted-foreground">
                A query is one chat completion that retrieves chunks. Document
                ingestion and embedding regenerations are billed separately
                under the document and chunk caps.
              </dd>
            </div>
            <div>
              <dt className="font-medium">
                Do you offer non-profit or open-source discounts?
              </dt>
              <dd className="mt-1 text-muted-foreground">
                Yes — email{" "}
                <a
                  href="mailto:hello@mongorag.dev"
                  className="underline underline-offset-4"
                >
                  hello@mongorag.dev
                </a>{" "}
                with proof and we will set you up.
              </dd>
            </div>
          </dl>
        </div>
      </section>
    </>
  );
}
