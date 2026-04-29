"use client";

import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[dashboard]", error);
  }, [error]);

  return (
    <div className="mx-auto flex max-w-md flex-col items-start gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6">
      <div className="grid size-9 place-items-center rounded-lg bg-destructive/10 text-destructive">
        <AlertTriangle className="size-4" aria-hidden="true" />
      </div>
      <div>
        <h2 className="font-heading text-lg font-medium text-foreground">
          Something went wrong
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          We could not load this page. The team has been notified.
        </p>
      </div>
      <Button variant="outline" onClick={reset}>
        Try again
      </Button>
    </div>
  );
}
