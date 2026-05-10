/**
 * Shared widget types.
 */

import type { WidgetFontKey } from "./fonts.js";

export type Position = "bottom-right" | "bottom-left";
export type ColorMode = "light" | "dark" | "auto";
export type RadiusToken = "none" | "sm" | "md" | "lg" | "full";
export type DensityToken = "compact" | "comfortable" | "spacious";
export type SizeToken = "sm" | "md" | "lg";
export type LauncherShape = "circle" | "rounded-square" | "pill";
export type LauncherIcon = "chat" | "sparkle" | "book" | "question" | "custom";

/**
 * Subset of theme tokens that may be overridden under `prefers-color-scheme:
 * dark` or `color_mode === "dark"`. Mirrors the Python WidgetDarkOverrides.
 */
export interface WidgetDarkOverrides {
  background?: string | null;
  surface?: string | null;
  foreground?: string | null;
  muted?: string | null;
  border?: string | null;
  primary?: string | null;
  primaryForeground?: string | null;
}

/**
 * Live widget config — what the widget runtime reads each render. Combines
 * authentication (apiKey/apiUrl/botId), identity (botName, welcomeMessage,
 * avatarUrl), and the full cosmetic theme surface that mirrors the API's
 * Python WidgetConfig.
 */
export interface WidgetConfig {
  // --- Connection / identity ---
  apiKey: string;
  apiUrl: string;
  botId?: string;
  botName: string;
  welcomeMessage: string;
  showBranding: boolean;

  // --- Cosmetic: existing surface (kept stable) ---
  primaryColor: string;
  position: Position;
  avatarUrl?: string | null;

  // --- Cosmetic: color tokens (#88) ---
  colorMode: ColorMode;
  background?: string | null;
  surface?: string | null;
  foreground?: string | null;
  muted?: string | null;
  border?: string | null;
  primaryForeground?: string | null;
  darkOverrides?: WidgetDarkOverrides | null;

  // --- Cosmetic: typography ---
  fontFamily: WidgetFontKey;
  displayFont?: WidgetFontKey | null;
  baseFontSize: SizeToken;

  // --- Cosmetic: shape & density ---
  radius: RadiusToken;
  density: DensityToken;
  launcherShape: LauncherShape;
  launcherSize: SizeToken;
  panelSize: SizeToken;

  // --- Cosmetic: branding & icons ---
  launcherIcon: LauncherIcon;
  launcherIconUrl?: string | null;
  showAvatarInMessages: boolean;
  brandingText?: string | null;
}

export interface ChatSource {
  document_title: string;
  heading_path: string[];
  snippet: string;
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  sources?: ChatSource[];
  pending?: boolean;
  /** Set when the bubble represents a terminal failure — drives retry UI. */
  error?: boolean;
}

export interface SSEEvent {
  type: string;
  content?: string;
  message?: string;
  sources?: ChatSource[];
  conversation_id?: string;
  [key: string]: unknown;
}
