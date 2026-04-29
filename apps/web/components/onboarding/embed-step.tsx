"use client";

import { ArrowRightIcon, CheckIcon, CopyIcon, RocketIcon } from "lucide-react";
import Link from "next/link";
import { useState, useSyncExternalStore } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface Props {
  keyPrefix: string | null;
  initialError: string | null;
}

const PLACEHOLDER_KEY = "mr_pk_xxxxxxxxxxxx";
const DEFAULT_BOT_SLUG = "default";

function buildSnippet(apiKey: string, botSlug: string): string {
  return [
    "<!-- MongoRAG embed widget -->",
    `<script src="https://cdn.mongorag.dev/widget.js"`,
    `        data-bot="${botSlug}"`,
    `        data-key="${apiKey}"`,
    `        async></script>`,
  ].join("\n");
}

function subscribeStorage(callback: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  window.addEventListener("storage", callback);
  return () => window.removeEventListener("storage", callback);
}

function readStoredKey(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.sessionStorage.getItem("mongorag.onboarding.apiKey");
  } catch {
    return null;
  }
}

export function EmbedStep({ keyPrefix, initialError }: Props) {
  const revealedKey = useSyncExternalStore(
    subscribeStorage,
    readStoredKey,
    () => null,
  );
  const [copied, setCopied] = useState(false);

  const apiKey =
    revealedKey ?? (keyPrefix ? `${keyPrefix}…` : PLACEHOLDER_KEY);
  const snippet = buildSnippet(apiKey, DEFAULT_BOT_SLUG);
  const hasRealKey = revealedKey !== null;

  async function copySnippet() {
    try {
      await navigator.clipboard.writeText(snippet);
      setCopied(true);
      toast.success("Snippet copied.");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Could not access the clipboard.");
    }
  }

  function finish() {
    try {
      sessionStorage.removeItem("mongorag.onboarding.apiKey");
      sessionStorage.removeItem("mongorag.onboarding.apiKeyPrefix");
    } catch {
      // ignore
    }
  }

  return (
    <div className="space-y-5">
      {initialError ? (
        <p
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive"
        >
          {initialError}
        </p>
      ) : null}

      {!hasRealKey && keyPrefix ? (
        <p
          role="status"
          className="rounded-lg border border-border bg-muted/20 px-4 py-3 text-sm text-muted-foreground"
        >
          We can&apos;t show the full key here for security. The snippet uses
          your key prefix as a placeholder — replace it with the full key from
          the API keys page before deploying.
        </p>
      ) : null}

      {!keyPrefix && !hasRealKey ? (
        <p
          role="status"
          className="rounded-lg border border-border bg-muted/20 px-4 py-3 text-sm text-muted-foreground"
        >
          You haven&apos;t created a key yet. The snippet uses a placeholder —{" "}
          <Link
            href="/onboarding/api-key"
            className="text-foreground underline-offset-4 hover:underline"
          >
            mint a key
          </Link>{" "}
          to make it live.
        </p>
      ) : null}

      <div className="overflow-hidden rounded-xl border border-border bg-foreground/[0.02]">
        <div className="flex items-center justify-between border-b border-border/70 bg-muted/40 px-4 py-2">
          <span className="font-mono text-[0.7rem] uppercase tracking-wider text-muted-foreground">
            index.html
          </span>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={copySnippet}
            aria-label={copied ? "Snippet copied" : "Copy snippet"}
          >
            {copied ? (
              <CheckIcon className="size-4" aria-hidden />
            ) : (
              <CopyIcon className="size-4" aria-hidden />
            )}
            <span className="ml-1.5 text-xs">{copied ? "Copied" : "Copy"}</span>
          </Button>
        </div>
        <pre className="overflow-x-auto p-5 font-mono text-[0.82rem] leading-6">
          <code>{snippet}</code>
        </pre>
      </div>

      <ul className="grid gap-3 text-sm text-muted-foreground sm:grid-cols-3">
        <li className="rounded-lg border border-border bg-background p-3">
          Streamed answers with citations back to the source chunk.
        </li>
        <li className="rounded-lg border border-border bg-background p-3">
          Tenant-scoped at the API layer — no data leakage.
        </li>
        <li className="rounded-lg border border-border bg-background p-3">
          Works in any framework — Next, Astro, Rails, plain HTML.
        </li>
      </ul>

      <div className="flex flex-col-reverse items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs text-muted-foreground">
          Need to test it? You can preview the widget from the bots page after
          you finish.
        </p>
        <Button
          asChild
          size="lg"
          className={cn("h-11", !hasRealKey && "")}
          onClick={finish}
        >
          <Link href="/dashboard">
            <RocketIcon aria-hidden className="mr-1.5 size-4" />
            Finish & open dashboard
            <ArrowRightIcon aria-hidden className="ml-1.5" />
          </Link>
        </Button>
      </div>
    </div>
  );
}
