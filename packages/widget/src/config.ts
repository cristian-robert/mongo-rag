/**
 * Configuration parsing for the embeddable widget.
 *
 * Sources, in priority order:
 *   1. window.MongoRAG  (explicit JS config)
 *   2. data-* attributes on the loading <script> tag
 *
 * Validation:
 *   - apiKey must be present and start with "mrag_"
 *   - apiUrl must be http(s); defaults to https://api.mongorag.com
 *   - position is whitelisted to prevent CSS injection
 *   - primaryColor is whitelisted to a safe regex (#hex, optional alpha, or rgb(a))
 *   - all theme tokens have safe defaults; unknown values fall back silently
 *
 * Most cosmetic theme tokens are sourced server-side (PublicBotConfig fetched
 * by publicBot.ts). The data-* surface is intentionally minimal — embedders
 * should use the dashboard rather than data attributes for branding.
 */

import { WIDGET_FONT_KEYS, type WidgetFontKey } from "./fonts.js";
import type {
  ColorMode,
  DensityToken,
  LauncherIcon,
  LauncherShape,
  Position,
  RadiusToken,
  SizeToken,
  WidgetConfig,
} from "./types.js";

const DEFAULT_API_URL = "https://api.mongorag.com";
const DEFAULT_PRIMARY_COLOR = "#0f172a";
const SAFE_COLOR = /^(#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?|rgb\([\d,\s]+\)|rgba\([\d,.\s]+\))$/;
const ALLOWED_POSITIONS: ReadonlySet<Position> = new Set(["bottom-right", "bottom-left"]);
const ALLOWED_COLOR_MODES: ReadonlySet<ColorMode> = new Set(["light", "dark", "auto"]);
const ALLOWED_RADII: ReadonlySet<RadiusToken> = new Set(["none", "sm", "md", "lg", "full"]);
const ALLOWED_DENSITIES: ReadonlySet<DensityToken> = new Set([
  "compact",
  "comfortable",
  "spacious",
]);
const ALLOWED_SIZES: ReadonlySet<SizeToken> = new Set(["sm", "md", "lg"]);
const ALLOWED_LAUNCHER_SHAPES: ReadonlySet<LauncherShape> = new Set([
  "circle",
  "rounded-square",
  "pill",
]);
const ALLOWED_LAUNCHER_ICONS: ReadonlySet<LauncherIcon> = new Set([
  "chat",
  "sparkle",
  "book",
  "question",
  "custom",
]);
// Strip C0 controls (0x00-0x1F) and DEL (0x7F).
const CONTROL_CHARS = /[\x00-\x1F\x7F]/g;

export interface RawConfigInput {
  apiKey?: string;
  apiUrl?: string;
  botId?: string;
  primaryColor?: string;
  botName?: string;
  welcomeMessage?: string;
  position?: string;
  showBranding?: boolean | string;
}

export class ConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ConfigError";
  }
}

export function parseScriptDataset(script: HTMLScriptElement): RawConfigInput {
  const ds = script.dataset;
  const out: RawConfigInput = {
    apiKey: ds.apiKey,
    apiUrl: ds.apiUrl,
    botId: ds.botId,
    primaryColor: ds.primaryColor,
    botName: ds.botName,
    welcomeMessage: ds.welcomeMessage,
    position: ds.position,
  };
  if (ds.showBranding !== undefined) out.showBranding = ds.showBranding;
  return out;
}

export function mergeConfig(
  primary: RawConfigInput | undefined,
  fallback: RawConfigInput | undefined,
): RawConfigInput {
  return { ...(fallback ?? {}), ...(primary ?? {}) };
}

function validateUrl(url: string): string {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    throw new ConfigError(`apiUrl is not a valid URL: ${url}`);
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new ConfigError(`apiUrl must be http or https: ${url}`);
  }
  // Strip trailing slash for predictable concatenation.
  return url.replace(/\/+$/, "");
}

export function safeColor(input: string | undefined, fallback: string): string {
  if (!input) return fallback;
  if (!SAFE_COLOR.test(input)) return fallback;
  return input;
}

export function safeOptionalColor(input: string | null | undefined): string | null {
  if (!input) return null;
  if (!SAFE_COLOR.test(input)) return null;
  return input;
}

export function safePosition(
  input: string | undefined,
  fallback: Position = "bottom-right",
): Position {
  if (input && ALLOWED_POSITIONS.has(input as Position)) {
    return input as Position;
  }
  return fallback;
}

export function safeColorMode(input: string | undefined, fallback: ColorMode = "light"): ColorMode {
  if (input && ALLOWED_COLOR_MODES.has(input as ColorMode)) return input as ColorMode;
  return fallback;
}

export function safeFont(input: string | undefined, fallback: WidgetFontKey = "system"): WidgetFontKey {
  if (input && (WIDGET_FONT_KEYS as readonly string[]).includes(input)) {
    return input as WidgetFontKey;
  }
  return fallback;
}

export function safeOptionalFont(input: string | null | undefined): WidgetFontKey | null {
  if (!input) return null;
  if (!(WIDGET_FONT_KEYS as readonly string[]).includes(input)) return null;
  return input as WidgetFontKey;
}

export function safeRadius(input: string | undefined, fallback: RadiusToken = "md"): RadiusToken {
  if (input && ALLOWED_RADII.has(input as RadiusToken)) return input as RadiusToken;
  return fallback;
}

export function safeDensity(
  input: string | undefined,
  fallback: DensityToken = "comfortable",
): DensityToken {
  if (input && ALLOWED_DENSITIES.has(input as DensityToken)) return input as DensityToken;
  return fallback;
}

export function safeSize(input: string | undefined, fallback: SizeToken = "md"): SizeToken {
  if (input && ALLOWED_SIZES.has(input as SizeToken)) return input as SizeToken;
  return fallback;
}

export function safeLauncherShape(
  input: string | undefined,
  fallback: LauncherShape = "circle",
): LauncherShape {
  if (input && ALLOWED_LAUNCHER_SHAPES.has(input as LauncherShape)) {
    return input as LauncherShape;
  }
  return fallback;
}

export function safeLauncherIcon(
  input: string | undefined,
  fallback: LauncherIcon = "chat",
): LauncherIcon {
  if (input && ALLOWED_LAUNCHER_ICONS.has(input as LauncherIcon)) {
    return input as LauncherIcon;
  }
  return fallback;
}

export function safeText(input: string | undefined, fallback: string, max = 200): string {
  if (!input) return fallback;
  return input.replace(CONTROL_CHARS, "").slice(0, max) || fallback;
}

export function safeOptionalText(input: string | null | undefined, max = 80): string | null {
  if (!input) return null;
  const cleaned = input.replace(CONTROL_CHARS, "").slice(0, max).trim();
  return cleaned || null;
}

export function safeOptionalHttpsUrl(input: string | null | undefined): string | null {
  if (!input) return null;
  const trimmed = input.trim();
  if (trimmed.length === 0 || trimmed.length > 500) return null;
  if (!trimmed.startsWith("https://")) return null;
  try {
    const u = new URL(trimmed);
    return u.protocol === "https:" ? trimmed : null;
  } catch {
    return null;
  }
}

function safeBool(input: boolean | string | undefined, fallback: boolean): boolean {
  if (typeof input === "boolean") return input;
  if (typeof input === "string") {
    if (input === "true") return true;
    if (input === "false") return false;
  }
  return fallback;
}

export function buildConfig(raw: RawConfigInput): WidgetConfig {
  const apiKey = (raw.apiKey ?? "").trim();
  if (!apiKey) {
    throw new ConfigError("Missing required apiKey (data-api-key)");
  }
  if (!apiKey.startsWith("mrag_")) {
    throw new ConfigError("apiKey must start with 'mrag_'");
  }

  const apiUrl = validateUrl(raw.apiUrl?.trim() || DEFAULT_API_URL);

  const result: WidgetConfig = {
    apiKey,
    apiUrl,
    botName: safeText(raw.botName?.trim(), "Assistant", 60),
    welcomeMessage: safeText(
      raw.welcomeMessage?.trim(),
      "Hi! Ask me anything about this site.",
      400,
    ),
    showBranding: safeBool(raw.showBranding, true),

    // Cosmetic — start at safe defaults; mergePublicConfig fills from server.
    primaryColor: safeColor(raw.primaryColor?.trim(), DEFAULT_PRIMARY_COLOR),
    position: safePosition(raw.position?.trim()),
    avatarUrl: null,
    colorMode: "light",
    background: null,
    surface: null,
    foreground: null,
    muted: null,
    border: null,
    primaryForeground: null,
    darkOverrides: null,
    fontFamily: "system",
    displayFont: null,
    baseFontSize: "md",
    radius: "md",
    density: "comfortable",
    launcherShape: "circle",
    launcherSize: "md",
    panelSize: "md",
    launcherIcon: "chat",
    launcherIconUrl: null,
    showAvatarInMessages: true,
    brandingText: null,
  };
  const botId = raw.botId?.trim();
  if (botId) result.botId = botId;
  return result;
}
