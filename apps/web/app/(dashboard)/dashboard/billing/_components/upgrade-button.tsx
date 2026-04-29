"use client";

import { useState, useTransition } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";

import { startCheckoutAction } from "../actions";
import type { ModelTier, PlanTier } from "@/lib/billing";

type Props = {
  plan: PlanTier;
  modelTier: ModelTier;
  label: string;
  variant?: "default" | "outline" | "secondary";
  disabled?: boolean;
  className?: string;
};

export function UpgradeButton({
  plan,
  modelTier,
  label,
  variant = "default",
  disabled = false,
  className,
}: Props) {
  const [pending, startTransition] = useTransition();
  const [submitted, setSubmitted] = useState(false);

  function onClick() {
    if (pending || submitted) return;
    setSubmitted(true);
    startTransition(async () => {
      const result = await startCheckoutAction({ plan, model_tier: modelTier });
      if (!result.ok) {
        setSubmitted(false);
        toast.error(result.error);
        return;
      }
      // Full-page navigation to Stripe-hosted checkout.
      window.location.assign(result.checkout_url);
    });
  }

  const busy = pending || submitted;

  return (
    <Button
      type="button"
      variant={variant}
      onClick={onClick}
      disabled={disabled || busy}
      aria-busy={busy}
      className={className}
    >
      {busy ? (
        <>
          <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
          Redirecting…
        </>
      ) : (
        label
      )}
    </Button>
  );
}
