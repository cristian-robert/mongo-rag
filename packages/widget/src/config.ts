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
 *   - primaryColor is whitelisted to a safe regex (#hex or rgb(a))
 */

import type { Position, WidgetConfig } from "./types.js";

const DEFAULT_API_URL = "https://api.mongorag.com";
const DEFAULT_PRIMARY_COLOR = "#0f172a";
const SAFE_COLOR = /^(#[0-9a-fA-F]{3,8}|rgb\([\d,\s]+\)|rgba\([\d,.\s]+\))$/;
const ALLOWED_POSITIONS: ReadonlySet<Position> = new Set(["bottom-right", "bottom-left"]);
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

export function safePosition(input: string | undefined, fallback: Position = "bottom-right"): Position {
  if (input && ALLOWED_POSITIONS.has(input as Position)) {
    return input as Position;
  }
  return fallback;
}

export function safeText(input: string | undefined, fallback: string, max = 200): string {
  if (!input) return fallback;
  return input.replace(CONTROL_CHARS, "").slice(0, max) || fallback;
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
    primaryColor: safeColor(raw.primaryColor?.trim(), DEFAULT_PRIMARY_COLOR),
    botName: safeText(raw.botName?.trim(), "Assistant", 60),
    welcomeMessage: safeText(
      raw.welcomeMessage?.trim(),
      "Hi! Ask me anything about this site.",
      400,
    ),
    position: safePosition(raw.position?.trim()),
    showBranding: safeBool(raw.showBranding, true),
  };
  const botId = raw.botId?.trim();
  if (botId) result.botId = botId;
  return result;
}
