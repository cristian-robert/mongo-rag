import type { Metadata } from "next";

import { ApiError } from "@/lib/api-client";
import { listApiKeys } from "@/lib/api-keys";

import { ApiKeysClient } from "./api-keys-client";

export const metadata: Metadata = {
  title: "API Keys — MongoRAG",
  description: "Create, list, and revoke API keys for the chat widget and programmatic access.",
};

// JWT minted server-side per request, never cache.
export const dynamic = "force-dynamic";

export default async function ApiKeysPage() {
  let initialError: string | null = null;
  let keys: Awaited<ReturnType<typeof listApiKeys>> = [];
  try {
    keys = await listApiKeys();
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
            Authentication
          </p>
          <h1 className="font-heading text-2xl leading-tight font-medium tracking-tight">
            API keys
          </h1>
          <p className="max-w-xl text-sm text-muted-foreground">
            Issue keys for the embed widget and any service that talks to your
            MongoRAG tenant. Each key carries a tenant-scoped permission set
            and can be revoked instantly.
          </p>
        </div>
      </header>

      <ApiKeysClient initialKeys={keys} initialError={initialError} />
    </div>
  );
}
