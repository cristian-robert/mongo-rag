import { CheckCircle2, XCircle } from "lucide-react";

import { cn } from "@/lib/utils";

export function CheckoutStatusBanner({ status }: { status: "success" | "cancelled" }) {
  const success = status === "success";
  const Icon = success ? CheckCircle2 : XCircle;
  const title = success ? "Payment received" : "Checkout cancelled";
  const message = success
    ? "Thanks — your subscription is being activated. It can take a moment to reflect here while we sync with Stripe."
    : "No charge was made. You can pick a different plan or model tier whenever you're ready.";

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "flex items-start gap-3 rounded-md border px-3 py-2.5 text-[0.82rem]",
        success
          ? "border-foreground/20 bg-foreground/5 text-foreground"
          : "border-border bg-muted/40 text-muted-foreground",
      )}
    >
      <Icon
        className={cn(
          "mt-0.5 size-4 shrink-0",
          success ? "text-foreground" : "text-muted-foreground",
        )}
        aria-hidden="true"
      />
      <div className="flex flex-col gap-0.5">
        <span className="font-medium text-foreground">{title}</span>
        <span>{message}</span>
      </div>
    </div>
  );
}
