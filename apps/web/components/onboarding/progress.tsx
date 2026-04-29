"use client";

import { CheckIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const STEPS = [
  { slug: "welcome", label: "Welcome", href: "/onboarding/welcome" },
  { slug: "document", label: "First document", href: "/onboarding/document" },
  { slug: "api-key", label: "API key", href: "/onboarding/api-key" },
  { slug: "embed", label: "Embed", href: "/onboarding/embed" },
] as const;

function currentIndex(pathname: string): number {
  const idx = STEPS.findIndex((s) => pathname.startsWith(s.href));
  return idx === -1 ? 0 : idx;
}

export function OnboardingProgress() {
  const pathname = usePathname();
  const active = currentIndex(pathname);
  const total = STEPS.length;
  const percent = Math.round(((active + 1) / total) * 100);

  return (
    <nav aria-label="Onboarding progress" className="space-y-3">
      <div className="flex items-center justify-between text-xs">
        <p className="font-mono uppercase tracking-wider text-muted-foreground">
          Step {active + 1} of {total}
        </p>
        <p className="text-muted-foreground" aria-live="polite">
          {percent}% complete
        </p>
      </div>
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        aria-label="Onboarding completion"
        className="h-1 w-full overflow-hidden rounded-full bg-border"
      >
        <div
          className="h-full bg-foreground transition-[width] duration-500 ease-out motion-reduce:transition-none"
          style={{ width: `${percent}%` }}
        />
      </div>
      <ol className="grid grid-cols-4 gap-2 text-xs sm:gap-3">
        {STEPS.map((step, idx) => {
          const isCurrent = idx === active;
          const isComplete = idx < active;
          return (
            <li key={step.slug}>
              <Link
                href={step.href}
                aria-current={isCurrent ? "step" : undefined}
                className={cn(
                  "flex items-center gap-2 rounded-md border border-transparent px-2 py-1.5 transition-colors",
                  "hover:border-border hover:bg-muted/40",
                  isCurrent && "border-border bg-muted/40 text-foreground",
                  !isCurrent && !isComplete && "text-muted-foreground",
                )}
              >
                <span
                  aria-hidden
                  className={cn(
                    "grid size-5 shrink-0 place-items-center rounded-full border text-[0.65rem] font-mono",
                    isComplete && "border-foreground bg-foreground text-background",
                    isCurrent && "border-foreground text-foreground",
                    !isCurrent && !isComplete && "border-border text-muted-foreground",
                  )}
                >
                  {isComplete ? <CheckIcon className="size-3" /> : idx + 1}
                </span>
                <span className="truncate">{step.label}</span>
              </Link>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
