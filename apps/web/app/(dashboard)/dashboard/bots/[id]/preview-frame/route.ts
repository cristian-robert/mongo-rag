/**
 * Preview iframe HTML route.
 *
 * Lives under (dashboard) so the existing auth middleware gates it —
 * only an authenticated tenant can request their bot's preview. The
 * route returns a minimal lorem-ipsum article page that loads the
 * widget bundle with `data-preview-tokens="<JSON>"` so the widget
 * boots in preview mode (no public-config fetch, chat input disabled).
 *
 * Tokens come in via `?t=<base64url(JSON)>`. Invalid / missing tokens
 * fall back to a default theme so the iframe never goes blank.
 */

import { NextResponse, type NextRequest } from "next/server";

import { defaultBotFormValues } from "@/lib/validations/bots";

const SAMPLE_BODY = `
<article class="prose">
  <h1>What we're previewing</h1>
  <p>This is a stripped sample page so you can see your widget against
  realistic body copy without saving and reloading. Click the launcher
  in the bottom corner to open the chat. The chat input is intentionally
  inert here — preview only.</p>
  <h2>Lorem ipsum</h2>
  <p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do
  eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim
  ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut
  aliquip ex ea commodo consequat.</p>
  <p>Duis aute irure dolor in reprehenderit in voluptate velit esse
  cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat
  cupidatat non proident, sunt in culpa qui officia deserunt mollit
  anim id est laborum.</p>
  <h2>Use the launcher</h2>
  <p>The widget renders in a Shadow DOM so the host page CSS can't
  bleed in. Updates from the form on the left re-build the iframe
  with the new tokens after a 250 ms debounce.</p>
</article>
`.trim();

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const url = new URL(request.url);
  const t = url.searchParams.get("t");
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "https://api.mongorag.com";

  let payload: Record<string, unknown> | null = null;
  if (t) {
    try {
      const decoded = decodeBase64UrlJson(t);
      if (decoded && typeof decoded === "object") {
        payload = decoded as Record<string, unknown>;
      }
    } catch {
      payload = null;
    }
  }

  const config = payload ?? buildDefaultPayload();

  const html = renderHtml({
    apiUrl,
    bot: {
      id: "preview",
      slug: "preview",
      name: typeof config.name === "string" ? config.name : "Assistant",
      welcome_message:
        typeof config.welcome_message === "string"
          ? config.welcome_message
          : defaultBotFormValues.welcome_message,
      widget_config: (config.widget_config as Record<string, unknown>) ?? {
        primary_color: "#0f172a",
        position: "bottom-right",
      },
    },
  });

  return new NextResponse(html, {
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      // Allow iframe embedding from same-origin (the dashboard).
      "X-Frame-Options": "SAMEORIGIN",
      "Cache-Control": "no-store",
    },
  });
}

function decodeBase64UrlJson(input: string): unknown {
  // Restore base64 padding + standard alphabet.
  const standard = input.replace(/-/g, "+").replace(/_/g, "/");
  const pad = standard.length % 4 === 0 ? "" : "=".repeat(4 - (standard.length % 4));
  const decoded = atob(standard + pad);
  return JSON.parse(decoded);
}

function buildDefaultPayload() {
  return {
    name: "Assistant",
    welcome_message: defaultBotFormValues.welcome_message,
    widget_config: defaultBotFormValues.widget_config,
  };
}

interface RenderArgs {
  apiUrl: string;
  bot: {
    id: string;
    slug: string;
    name: string;
    welcome_message: string;
    widget_config: Record<string, unknown>;
  };
}

function renderHtml({ apiUrl, bot }: RenderArgs) {
  // The widget bundle reads data-preview-tokens as JSON, calls
  // configFromPublicOnly under the hood, and skips the public fetch.
  // The token rides in a single-quoted HTML attribute, so apostrophes
  // in user-controlled fields (welcome_message, branding_text, name)
  // would terminate the attribute early and make the widget bundle's
  // JSON.parse throw — the launcher then never mounts and no settings
  // changes propagate. Escape `'`, `<`, and `--` to keep the attribute
  // and any nested </script> sequences safe.
  const tokensJson = JSON.stringify(bot)
    .replace(/</g, "\\u003c")
    .replace(/--/g, "-\\u002d")
    .replace(/'/g, "\\u0027");

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Widget preview</title>
  <style>
    :root {
      color-scheme: light dark;
      font-family: ui-sans-serif, system-ui, sans-serif;
    }
    body {
      margin: 0;
      padding: 32px;
      background: #fafafa;
      color: #1f2937;
      max-width: 720px;
      margin-inline: auto;
    }
    .prose h1 { font-size: 1.5rem; font-weight: 600; margin: 0 0 0.75rem; }
    .prose h2 { font-size: 1.125rem; font-weight: 600; margin: 1.5rem 0 0.5rem; }
    .prose p { margin: 0 0 0.875rem; line-height: 1.6; color: #374151; }
    @media (prefers-color-scheme: dark) {
      body { background: #0d0d10; color: #e7e7ea; }
      .prose p { color: #c2c2c8; }
    }
    /* The widget mounts a button — disable form pointer events so
       customers can't accidentally try to chat from preview. */
    [data-mongorag-widget] form { pointer-events: none; opacity: 0.7; }
    [data-mongorag-widget] textarea { pointer-events: auto; }
  </style>
</head>
<body>
  ${SAMPLE_BODY}
  <script
    src="/widget.js"
    data-api-url="${apiUrl}"
    data-preview-tokens='${tokensJson}'></script>
</body>
</html>`;
}
