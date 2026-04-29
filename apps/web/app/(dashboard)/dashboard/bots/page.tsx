import type { Metadata } from "next";
import Link from "next/link";
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api-client";
import { listBots } from "@/lib/bots";

import { BotsTable } from "./bots-table";

export const metadata: Metadata = {
  title: "Bots — MongoRAG",
  description:
    "Configure chatbots, scope their document sources, and generate embed snippets.",
};

// Per-request JWT minted server-side; never cache.
export const dynamic = "force-dynamic";

export default async function BotsPage() {
  let initialError: string | null = null;
  let bots: Awaited<ReturnType<typeof listBots>> = [];
  try {
    bots = await listBots();
  } catch (err) {
    initialError =
      err instanceof ApiError
        ? err.message
        : "Could not reach the API. Try again in a moment.";
  }

  return (
    <div className="mx-auto w-full max-w-5xl space-y-8 px-6 py-10">
      <header className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-1">
          <p className="font-mono text-[0.7rem] tracking-[0.2em] text-muted-foreground uppercase">
            Configuration
          </p>
          <h1 className="font-heading text-2xl leading-tight font-medium tracking-tight">
            Bots
          </h1>
          <p className="max-w-xl text-sm text-muted-foreground">
            Each bot has its own personality, document scope, and widget
            appearance. Create as many as you need — for support, sales, or
            internal knowledge — and embed them with a single script tag.
          </p>
        </div>
        <Button
          render={(props) => (
            <Link {...props} href="/dashboard/bots/new" />
          )}
        >
          <Plus />
          New bot
        </Button>
      </header>

      {initialError ? (
        <div
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive"
        >
          {initialError}
        </div>
      ) : (
        <BotsTable bots={bots} />
      )}
    </div>
  );
}
