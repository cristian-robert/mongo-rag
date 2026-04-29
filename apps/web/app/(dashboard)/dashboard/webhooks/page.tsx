import type { Metadata } from "next";

import { ApiError } from "@/lib/api-client";
import { listWebhooks } from "@/lib/webhooks";

import { WebhooksClient } from "./webhooks-client";

export const metadata: Metadata = {
  title: "Webhooks — MongoRAG",
  description:
    "Subscribe HTTPS endpoints to events in your MongoRAG tenant. HMAC-signed deliveries with retries and an audit log.",
};

// JWT minted server-side per request, never cache.
export const dynamic = "force-dynamic";

export default async function WebhooksPage() {
  let initialError: string | null = null;
  let webhooks: Awaited<ReturnType<typeof listWebhooks>> = [];
  try {
    webhooks = await listWebhooks();
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
            Integrations
          </p>
          <h1 className="font-heading text-2xl leading-tight font-medium tracking-tight">
            Webhooks
          </h1>
          <p className="max-w-xl text-sm text-muted-foreground">
            Receive HMAC-signed POSTs when documents ingest, conversations
            finish, or your subscription changes. Failed deliveries retry with
            exponential backoff, and every attempt is logged for replay.
          </p>
        </div>
      </header>

      <WebhooksClient
        initialWebhooks={webhooks}
        initialError={initialError}
      />
    </div>
  );
}
