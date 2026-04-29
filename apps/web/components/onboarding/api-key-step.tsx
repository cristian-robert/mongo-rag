"use client";

import { ArrowRightIcon, CheckIcon, CopyIcon, KeyRoundIcon } from "lucide-react";
import Link from "next/link";
import { useState, useTransition } from "react";
import { toast } from "sonner";

import { createApiKeyAction } from "@/app/(dashboard)/dashboard/api-keys/actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

interface Props {
  initialError: string | null;
  existingPrefix: string | null;
}

export function ApiKeyStep({ initialError, existingPrefix }: Props) {
  const [name, setName] = useState("Embed widget");
  const [pending, startTransition] = useTransition();
  const [rawKey, setRawKey] = useState<string | null>(null);
  const [keyPrefix, setKeyPrefix] = useState<string | null>(existingPrefix);
  const [copied, setCopied] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  function handleCreate() {
    setFormError(null);
    const trimmed = name.trim();
    if (trimmed.length < 2) {
      setFormError("Give the key a memorable name (at least 2 characters).");
      return;
    }

    startTransition(async () => {
      const result = await createApiKeyAction({
        name: trimmed,
        permissions: ["chat", "search"],
      });
      if (!result.ok) {
        setFormError(result.error);
        toast.error(result.error);
        return;
      }
      setRawKey(result.key.raw_key);
      setKeyPrefix(result.key.key_prefix);
      try {
        sessionStorage.setItem("mongorag.onboarding.apiKey", result.key.raw_key);
        sessionStorage.setItem(
          "mongorag.onboarding.apiKeyPrefix",
          result.key.key_prefix,
        );
      } catch {
        // sessionStorage can be unavailable (private mode, ITP); harmless.
      }
      toast.success("API key created.");
    });
  }

  async function copyKey() {
    if (!rawKey) return;
    try {
      await navigator.clipboard.writeText(rawKey);
      setCopied(true);
      toast.success("Copied to clipboard.");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Could not access the clipboard.");
    }
  }

  if (rawKey) {
    return (
      <div className="space-y-5">
        <div
          role="alert"
          className="flex flex-col gap-3 rounded-xl border border-border bg-foreground/[0.02] p-5"
        >
          <div className="flex items-center gap-2 text-sm">
            <span
              aria-hidden
              className="grid size-7 place-items-center rounded-md border border-border bg-background"
            >
              <KeyRoundIcon className="size-3.5" />
            </span>
            <p className="font-medium">Key created — copy it now.</p>
          </div>
          <p className="text-xs text-muted-foreground">
            We won&apos;t show this value again. The dashboard only stores a
            hashed version.
          </p>
          <div className="flex items-center gap-2 rounded-lg border border-border bg-background p-2.5">
            <code className="flex-1 truncate font-mono text-sm">{rawKey}</code>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={copyKey}
              aria-label={copied ? "Copied" : "Copy API key to clipboard"}
            >
              {copied ? (
                <CheckIcon className="size-4" aria-hidden />
              ) : (
                <CopyIcon className="size-4" aria-hidden />
              )}
              <span className="ml-1.5">{copied ? "Copied" : "Copy"}</span>
            </Button>
          </div>
        </div>

        <div className="flex flex-col-reverse items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-muted-foreground">
            Prefix <code className="font-mono">{keyPrefix}</code> · keep the
            full value safe.
          </p>
          <Button asChild size="lg" className="h-11">
            <Link href="/onboarding/embed">
              Continue to embed
              <ArrowRightIcon aria-hidden className="ml-1.5" />
            </Link>
          </Button>
        </div>
      </div>
    );
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

      {existingPrefix ? (
        <p
          role="status"
          className="rounded-lg border border-border bg-muted/20 px-4 py-3 text-sm text-muted-foreground"
        >
          You already have a live key starting with{" "}
          <code className="font-mono text-foreground">{existingPrefix}</code>.
          Create another one for this embed if you&apos;d like, or skip ahead.
        </p>
      ) : null}

      <div className="flex flex-col gap-2">
        <Label htmlFor="onboarding-key-name">Key name</Label>
        <Input
          id="onboarding-key-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Marketing site embed"
          autoComplete="off"
          maxLength={100}
          disabled={pending}
          aria-invalid={formError ? true : undefined}
          aria-describedby={formError ? "onboarding-key-name-error" : undefined}
        />
        {formError ? (
          <p
            id="onboarding-key-name-error"
            role="alert"
            className="text-sm text-destructive"
          >
            {formError}
          </p>
        ) : (
          <p className="text-xs text-muted-foreground">
            A label so you can recognize the key in the dashboard later.
          </p>
        )}
      </div>

      <div className="flex flex-col-reverse items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Button asChild variant="ghost" type="button">
          <Link href="/onboarding/embed">Skip for now</Link>
        </Button>
        <Button
          type="button"
          onClick={handleCreate}
          disabled={pending}
          size="lg"
          className={cn("h-11", pending && "opacity-80")}
        >
          {pending ? "Creating…" : "Create key"}
        </Button>
      </div>
    </div>
  );
}
