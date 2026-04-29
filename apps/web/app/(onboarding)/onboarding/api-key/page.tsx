import type { Metadata } from "next";

import { ApiError } from "@/lib/api-client";
import { listApiKeys } from "@/lib/api-keys";

import { ApiKeyStep } from "@/components/onboarding/api-key-step";

export const metadata: Metadata = {
  title: "Create your API key — MongoRAG",
  description: "Mint a tenant-scoped key for the embed widget.",
};

export const dynamic = "force-dynamic";

export default async function OnboardingApiKeyPage() {
  let initialError: string | null = null;
  let existingPrefix: string | null = null;

  try {
    const keys = await listApiKeys();
    const live = keys.find((k) => !k.is_revoked);
    existingPrefix = live?.key_prefix ?? null;
  } catch (err) {
    initialError =
      err instanceof ApiError
        ? err.message
        : "Could not reach the API. You can still create a key.";
  }

  return (
    <section aria-labelledby="onboarding-api-key" className="space-y-6">
      <header className="space-y-2">
        <p className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
          Step 03 — API key
        </p>
        <h1
          id="onboarding-api-key"
          className="text-3xl font-light tracking-tight sm:text-4xl"
        >
          Mint a key for your embed.
        </h1>
        <p className="max-w-prose text-muted-foreground">
          Keys are tenant-scoped. The full key is shown once — copy it now and
          store it somewhere safe. You can revoke and re-issue from the
          dashboard at any time.
        </p>
      </header>

      <ApiKeyStep
        initialError={initialError}
        existingPrefix={existingPrefix}
      />
    </section>
  );
}
