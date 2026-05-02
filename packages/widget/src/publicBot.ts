/**
 * Public bot config — fetched anonymously at widget boot.
 *
 * The widget calls `GET ${apiUrl}/api/v1/bots/public/{botId}` so dashboard
 * edits to a bot's name, welcome message, primary color, and position
 * propagate without the customer needing to update the embed snippet.
 *
 * Precedence: `data-*` attributes on the embed `<script>` tag are EXPLICIT
 * customer intent and always win over server values. Server values fill in
 * fields the customer did not set. Network/parse failures are silent and
 * non-blocking — the widget keeps the `data-*` defaults already rendered.
 *
 * The backend response surface is locked down server-side (see
 * `apps/api/src/services/bot.py:172` and `apps/api/tests/test_bot_router.py`)
 * so this module never sees `system_prompt`, `document_filter`, or
 * `tenant_id`. We additionally re-validate `primary_color` and `position`
 * here through the same `safeColor`/`safePosition` filters used for raw
 * embed values, so an upstream regression cannot inject unsafe styles.
 */

import { safeColor, safePosition, safeText, type RawConfigInput } from "./config.js";
import type { Position, WidgetConfig } from "./types.js";

export interface PublicBotWidgetConfig {
  primary_color: string;
  position: string;
  avatar_url?: string | null;
}

export interface PublicBotConfig {
  id: string;
  slug: string;
  name: string;
  welcome_message: string;
  widget_config: PublicBotWidgetConfig;
}

function isPublicBotConfig(value: unknown): value is PublicBotConfig {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  if (typeof v.id !== "string") return false;
  if (typeof v.slug !== "string") return false;
  if (typeof v.name !== "string") return false;
  if (typeof v.welcome_message !== "string") return false;
  const wc = v.widget_config;
  if (!wc || typeof wc !== "object") return false;
  const wcr = wc as Record<string, unknown>;
  if (typeof wcr.primary_color !== "string") return false;
  if (typeof wcr.position !== "string") return false;
  return true;
}

export async function fetchPublicBotConfig(
  apiUrl: string,
  botId: string,
  signal?: AbortSignal,
): Promise<PublicBotConfig | null> {
  const base = apiUrl.replace(/\/+$/, "");
  const url = `${base}/api/v1/bots/public/${encodeURIComponent(botId)}`;
  try {
    const response = await fetch(url, {
      method: "GET",
      cache: "force-cache",
      credentials: "omit",
      mode: "cors",
      ...(signal ? { signal } : {}),
    });
    if (!response.ok) return null;
    const data: unknown = await response.json();
    if (!isPublicBotConfig(data)) return null;
    return data;
  } catch {
    return null;
  }
}

/**
 * Merge server values into the live widget config without overriding any
 * field the embed script set explicitly. `raw` is the raw embed input
 * BEFORE defaults were applied — fields the embed didn't touch are
 * `undefined` there, so we adopt the server value for those.
 */
export function mergePublicConfig(
  current: WidgetConfig,
  raw: RawConfigInput,
  server: PublicBotConfig,
): WidgetConfig {
  const next: WidgetConfig = { ...current };

  if (raw.botName === undefined) {
    next.botName = safeText(server.name, current.botName, 60);
  }

  if (raw.welcomeMessage === undefined) {
    next.welcomeMessage = safeText(server.welcome_message, current.welcomeMessage, 400);
  }

  if (raw.primaryColor === undefined) {
    next.primaryColor = safeColor(server.widget_config.primary_color, current.primaryColor);
  }

  if (raw.position === undefined) {
    next.position = safePosition(server.widget_config.position, current.position as Position);
  }

  return next;
}
