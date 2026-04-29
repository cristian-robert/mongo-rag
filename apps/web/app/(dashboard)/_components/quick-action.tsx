import Link from "next/link";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function QuickAction({
  href,
  label,
  description,
  icon,
}: {
  href: string;
  label: string;
  description: string;
  icon: ReactNode;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "group flex items-start gap-3 rounded-xl border border-border bg-card p-4 text-left transition-colors",
        "hover:border-foreground/30 hover:bg-muted/40",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      )}
    >
      <span
        aria-hidden="true"
        className="grid size-9 shrink-0 place-items-center rounded-lg bg-foreground text-background transition-transform group-hover:-rotate-3"
      >
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <div className="font-heading text-[0.95rem] font-medium tracking-tight text-foreground">
          {label}
        </div>
        <p className="mt-0.5 text-[0.82rem] text-muted-foreground">
          {description}
        </p>
      </div>
    </Link>
  );
}
