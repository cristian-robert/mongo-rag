"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";

interface Props {
  botId: string;
  apiKey?: string;
  cdnUrl?: string;
}

const DEFAULT_CDN_URL =
  process.env.NEXT_PUBLIC_WIDGET_URL ?? "https://cdn.mongorag.com/widget.js";

export function EmbedSnippet({ botId, apiKey, cdnUrl }: Props) {
  const [copied, setCopied] = useState(false);
  const url = cdnUrl ?? DEFAULT_CDN_URL;
  const apiKeyValue = apiKey ?? "YOUR_API_KEY";

  // Build the snippet without template literals to avoid injecting
  // characters that would need escaping in HTML attributes.
  const snippet = `<script
  src="${url}"
  data-api-key="${apiKeyValue}"
  data-bot-id="${botId}"
  defer
></script>`;

  async function copy() {
    try {
      await navigator.clipboard.writeText(snippet);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // ignore — older browsers will see no feedback
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">Embed snippet</p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={copy}
          aria-label="Copy embed snippet"
        >
          {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <pre className="overflow-x-auto rounded-lg border border-border/60 bg-muted/40 p-3 text-xs leading-relaxed">
        <code>{snippet}</code>
      </pre>
      {!apiKey && (
        <p className="text-xs text-muted-foreground">
          Replace <code className="font-mono">YOUR_API_KEY</code> with a key
          from the{" "}
          <a
            href="/dashboard/api-keys"
            className="underline underline-offset-2 hover:text-foreground"
          >
            API Keys
          </a>{" "}
          page.
        </p>
      )}
    </div>
  );
}
