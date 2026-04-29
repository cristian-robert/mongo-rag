import type { Metadata } from "next";

import { ApiError } from "@/lib/api-client";
import { listApiKeys } from "@/lib/api-keys";

import { EmbedStep } from "@/components/onboarding/embed-step";

export const metadata: Metadata = {
  title: "Copy your embed snippet — MongoRAG",
  description: "Drop the widget script tag onto any page.",
};

export const dynamic = "force-dynamic";

export default async function OnboardingEmbedPage() {
  let keyPrefix: string | null = null;
  let initialError: string | null = null;

  try {
    const keys = await listApiKeys();
    const live = keys.find((k) => !k.is_revoked);
    keyPrefix = live?.key_prefix ?? null;
  } catch (err) {
    initialError =
      err instanceof ApiError
        ? err.message
        : "Could not load your keys. The snippet below uses a placeholder.";
  }

  return (
    <section aria-labelledby="onboarding-embed" className="space-y-6">
      <header className="space-y-2">
        <p className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
          Step 04 — Embed
        </p>
        <h1
          id="onboarding-embed"
          className="text-3xl font-light tracking-tight sm:text-4xl"
        >
          Drop the widget on your site.
        </h1>
        <p className="max-w-prose text-muted-foreground">
          Paste this snippet into the <code>{`<head>`}</code> of any page. The
          widget loads asynchronously and authenticates with your tenant key.
        </p>
      </header>

      <EmbedStep keyPrefix={keyPrefix} initialError={initialError} />
    </section>
  );
}
