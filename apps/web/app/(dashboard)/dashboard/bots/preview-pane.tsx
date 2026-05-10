"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import type { CreateBotFormData } from "@/lib/validations/bots";

interface PreviewPaneProps {
  botId: string;
  draft: Pick<CreateBotFormData, "name" | "welcome_message" | "widget_config">;
}

const DEBOUNCE_MS = 250;

/**
 * Side-by-side preview pane.
 *
 * Hydration: encoding the draft uses `btoa`, which is browser-only. SSR
 * pre-renders this client component as well, so we must NOT compute the
 * token during render. We start with an empty token (matching SSR) and
 * fill it in once mounted; the iframe then debounce-reloads on every
 * draft change.
 */
export function PreviewPane({ botId, draft }: PreviewPaneProps) {
  const frameRef = useRef<HTMLIFrameElement | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Encode lazily after mount so the SSR + first-client render match.
  const token = useMemo(() => (mounted ? encodeDraft(draft) : ""), [mounted, draft]);

  const url = `/dashboard/bots/${botId}/preview-frame${token ? `?t=${token}` : ""}`;

  useEffect(() => {
    if (!mounted) return;
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      if (frameRef.current) frameRef.current.src = url;
    }, DEBOUNCE_MS);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [url, mounted]);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Live preview</span>
        <Link
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          Open in new tab ↗
        </Link>
      </div>
      <div className="overflow-hidden rounded-xl border border-border/60 bg-muted/30">
        <iframe
          ref={frameRef}
          title="Widget preview"
          className="h-[640px] w-full bg-background"
        />
      </div>
      <p className="text-xs text-muted-foreground">
        Reflects unsaved form changes. Chat is disabled here — save and embed
        on a real page to talk to the bot.
      </p>
    </div>
  );
}

function encodeDraft(draft: PreviewPaneProps["draft"]): string {
  try {
    const json = JSON.stringify(draft);
    if (typeof btoa === "undefined") return "";
    const b64 = btoa(unescape(encodeURIComponent(json)));
    return b64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  } catch {
    return "";
  }
}
