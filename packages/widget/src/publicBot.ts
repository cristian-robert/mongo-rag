/**
 * Public bot config — fetched anonymously at widget boot.
 *
 * The widget calls `GET ${apiUrl}/api/v1/bots/public/{botId}` so dashboard
 * edits to a bot's name, welcome message, theme tokens, and position
 * propagate without the customer needing to update the embed snippet.
 *
 * Precedence: `data-*` attributes on the embed `<script>` tag are EXPLICIT
 * customer intent and always win over server values. Server values fill in
 * fields the customer did not set. Network/parse failures are silent and
 * non-blocking — the widget keeps the `data-*` defaults already rendered.
 *
 * The backend response surface is locked down server-side (see
 * `apps/api/src/services/bot.py` and the pinned-allowlist test in
 * `apps/api/tests/test_bot_router.py::test_public_bot_response_has_strict_allowlist`)
 * so this module never sees `system_prompt`, `document_filter`, or
 * `tenant_id`. We additionally re-validate every received value here so
 * an upstream regression cannot inject unsafe styles.
 */

import {
  safeColor,
  safeColorMode,
  safeDensity,
  safeFont,
  safeLauncherIcon,
  safeLauncherShape,
  safeOptionalColor,
  safeOptionalFont,
  safeOptionalHttpsUrl,
  safeOptionalText,
  safePosition,
  safeRadius,
  safeSize,
  safeText,
  type RawConfigInput,
} from "./config.js";
import type { Position, WidgetConfig, WidgetDarkOverrides } from "./types.js";

export interface PublicBotWidgetConfig {
  primary_color?: string;
  position?: string;
  avatar_url?: string | null;
  // New (mirrors apps/api/src/models/bot.py WidgetConfig)
  color_mode?: string;
  background?: string | null;
  surface?: string | null;
  foreground?: string | null;
  muted?: string | null;
  border?: string | null;
  primary_foreground?: string | null;
  dark_overrides?: PublicDarkOverrides | null;
  font_family?: string;
  display_font?: string | null;
  base_font_size?: string;
  radius?: string;
  density?: string;
  launcher_shape?: string;
  launcher_size?: string;
  panel_size?: string;
  launcher_icon?: string;
  launcher_icon_url?: string | null;
  show_avatar_in_messages?: boolean;
  branding_text?: string | null;
}

export interface PublicDarkOverrides {
  background?: string | null;
  surface?: string | null;
  foreground?: string | null;
  muted?: string | null;
  border?: string | null;
  primary?: string | null;
  primary_foreground?: string | null;
}

export interface PublicBotConfig {
  id: string;
  slug: string;
  name: string;
  welcome_message: string;
  widget_config: PublicBotWidgetConfig;
}

function isObject(v: unknown): v is Record<string, unknown> {
  return !!v && typeof v === "object" && !Array.isArray(v);
}

function isPublicBotConfig(value: unknown): value is PublicBotConfig {
  if (!isObject(value)) return false;
  if (typeof value.id !== "string") return false;
  if (typeof value.slug !== "string") return false;
  if (typeof value.name !== "string") return false;
  if (typeof value.welcome_message !== "string") return false;
  if (!isObject(value.widget_config)) return false;
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

function parseDarkOverrides(raw: PublicDarkOverrides | null | undefined): WidgetDarkOverrides | null {
  if (!raw) return null;
  const out: WidgetDarkOverrides = {
    background: safeOptionalColor(raw.background ?? undefined),
    surface: safeOptionalColor(raw.surface ?? undefined),
    foreground: safeOptionalColor(raw.foreground ?? undefined),
    muted: safeOptionalColor(raw.muted ?? undefined),
    border: safeOptionalColor(raw.border ?? undefined),
    primary: safeOptionalColor(raw.primary ?? undefined),
    primaryForeground: safeOptionalColor(raw.primary_foreground ?? undefined),
  };
  // If every field came back null after validation, drop the object.
  const hasAny = Object.values(out).some((v) => v !== null);
  return hasAny ? out : null;
}

/**
 * Merge server values into the live widget config without overriding any
 * field the embed script set explicitly. `raw` is the raw embed input
 * BEFORE defaults were applied — fields the embed didn't touch are
 * `undefined` there, so we adopt the server value for those.
 *
 * For the new theme tokens (#88), data-* attributes don't (yet) carry
 * them — the embed only ships connection + the legacy primaryColor /
 * position. Server values for the new tokens always apply.
 */
export function mergePublicConfig(
  current: WidgetConfig,
  raw: RawConfigInput,
  server: PublicBotConfig,
): WidgetConfig {
  const next: WidgetConfig = { ...current };
  const wc = server.widget_config;

  if (raw.botName === undefined) {
    next.botName = safeText(server.name, current.botName, 60);
  }

  if (raw.welcomeMessage === undefined) {
    next.welcomeMessage = safeText(server.welcome_message, current.welcomeMessage, 400);
  }

  if (raw.primaryColor === undefined && wc.primary_color) {
    next.primaryColor = safeColor(wc.primary_color, current.primaryColor);
  }

  if (raw.position === undefined && wc.position) {
    next.position = safePosition(wc.position, current.position as Position);
  }

  // Theme tokens that don't have a data-* equivalent — server is the
  // source of truth, fall back to current (defaults) when absent.
  next.avatarUrl = safeOptionalHttpsUrl(wc.avatar_url) ?? current.avatarUrl ?? null;
  next.colorMode = safeColorMode(wc.color_mode, current.colorMode);
  next.background = safeOptionalColor(wc.background) ?? current.background ?? null;
  next.surface = safeOptionalColor(wc.surface) ?? current.surface ?? null;
  next.foreground = safeOptionalColor(wc.foreground) ?? current.foreground ?? null;
  next.muted = safeOptionalColor(wc.muted) ?? current.muted ?? null;
  next.border = safeOptionalColor(wc.border) ?? current.border ?? null;
  next.primaryForeground =
    safeOptionalColor(wc.primary_foreground) ?? current.primaryForeground ?? null;
  next.darkOverrides = parseDarkOverrides(wc.dark_overrides ?? null) ?? current.darkOverrides ?? null;

  next.fontFamily = safeFont(wc.font_family, current.fontFamily);
  next.displayFont = safeOptionalFont(wc.display_font) ?? current.displayFont ?? null;
  next.baseFontSize = safeSize(wc.base_font_size, current.baseFontSize);

  next.radius = safeRadius(wc.radius, current.radius);
  next.density = safeDensity(wc.density, current.density);
  next.launcherShape = safeLauncherShape(wc.launcher_shape, current.launcherShape);
  next.launcherSize = safeSize(wc.launcher_size, current.launcherSize);
  next.panelSize = safeSize(wc.panel_size, current.panelSize);

  next.launcherIcon = safeLauncherIcon(wc.launcher_icon, current.launcherIcon);
  next.launcherIconUrl =
    safeOptionalHttpsUrl(wc.launcher_icon_url) ?? current.launcherIconUrl ?? null;
  next.showAvatarInMessages =
    typeof wc.show_avatar_in_messages === "boolean"
      ? wc.show_avatar_in_messages
      : current.showAvatarInMessages;
  next.brandingText = safeOptionalText(wc.branding_text) ?? current.brandingText ?? null;

  return next;
}

/**
 * Build a WidgetConfig from a full PublicBotConfig only (no embed input).
 * Used by the dashboard preview iframe and `bootWithConfig` API.
 *
 * Caller supplies apiKey / apiUrl since these are environment-specific
 * and not part of the public bot payload.
 */
export function configFromPublicOnly(
  base: { apiKey: string; apiUrl: string; botId?: string; showBranding?: boolean },
  server: PublicBotConfig,
): WidgetConfig {
  const wc = server.widget_config;
  return {
    apiKey: base.apiKey,
    apiUrl: base.apiUrl,
    botId: base.botId,
    botName: safeText(server.name, "Assistant", 60),
    welcomeMessage: safeText(server.welcome_message, "Hi!", 400),
    showBranding: base.showBranding ?? true,
    primaryColor: safeColor(wc.primary_color, "#0f172a"),
    position: safePosition(wc.position),
    avatarUrl: safeOptionalHttpsUrl(wc.avatar_url),
    colorMode: safeColorMode(wc.color_mode),
    background: safeOptionalColor(wc.background),
    surface: safeOptionalColor(wc.surface),
    foreground: safeOptionalColor(wc.foreground),
    muted: safeOptionalColor(wc.muted),
    border: safeOptionalColor(wc.border),
    primaryForeground: safeOptionalColor(wc.primary_foreground),
    darkOverrides: parseDarkOverrides(wc.dark_overrides ?? null),
    fontFamily: safeFont(wc.font_family),
    displayFont: safeOptionalFont(wc.display_font),
    baseFontSize: safeSize(wc.base_font_size),
    radius: safeRadius(wc.radius),
    density: safeDensity(wc.density),
    launcherShape: safeLauncherShape(wc.launcher_shape),
    launcherSize: safeSize(wc.launcher_size),
    panelSize: safeSize(wc.panel_size),
    launcherIcon: safeLauncherIcon(wc.launcher_icon),
    launcherIconUrl: safeOptionalHttpsUrl(wc.launcher_icon_url),
    showAvatarInMessages:
      typeof wc.show_avatar_in_messages === "boolean" ? wc.show_avatar_in_messages : true,
    brandingText: safeOptionalText(wc.branding_text),
  };
}
