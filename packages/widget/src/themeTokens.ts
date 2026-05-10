/**
 * Token derivation: WidgetConfig → CSS-ready ThemeTokens.
 *
 * Pure functions only. No DOM access, no side effects. The return value
 * is fed into buildStyles() to produce a CSS string for the Shadow DOM.
 *
 * Naming: keep tokens flat and CSS-variable-ready (kebab-case keys
 * downstream) — it makes the styles.ts template a one-line interpolation
 * per variable.
 */

import { fontStack } from "./fonts.js";
import type { WidgetConfig, WidgetDarkOverrides } from "./types.js";

export interface ThemeTokens {
  // Colors
  background: string;
  surface: string;
  foreground: string;
  muted: string;
  border: string;
  primary: string;
  primaryForeground: string;
  // Typography
  fontStack: string;
  displayFontStack: string | null;
  baseFontSizePx: number;
  // Shape — message corner radius (asymmetric corner stays handled in CSS)
  radiusMessagePx: number;
  radiusPanelPx: number;
  // Density — vertical/horizontal padding scale
  panelPaddingPx: number;
  messageGapPx: number;
  // Dimensions
  panelWidthPx: number;
  panelHeightPx: number;
  launcherSizePx: number;
  launcherRadiusPx: number;
  // Mode class on host
  colorModeClass: "mrag-mode-light" | "mrag-mode-dark" | "mrag-mode-auto";
}

const DEFAULT_LIGHT = {
  background: "#ffffff",
  surface: "#f8fafc",
  foreground: "#0f172a",
  muted: "#64748b",
  border: "rgba(15, 23, 42, 0.08)",
  primaryForeground: "#ffffff",
};

const DEFAULT_DARK = {
  background: "#0a0a0c",
  surface: "#16161a",
  foreground: "#f1f1f3",
  muted: "#9aa0aa",
  border: "rgba(241, 241, 243, 0.10)",
  primaryForeground: "#ffffff",
};

const SIZE_FONT_PX: Record<"sm" | "md" | "lg", number> = {
  sm: 13,
  md: 14,
  lg: 15,
};

const RADIUS_PX: Record<"none" | "sm" | "md" | "lg" | "full", { msg: number; panel: number }> = {
  none: { msg: 0, panel: 0 },
  sm: { msg: 6, panel: 8 },
  md: { msg: 12, panel: 14 },
  lg: { msg: 18, panel: 20 },
  full: { msg: 22, panel: 28 },
};

const DENSITY_PADDING_PX: Record<"compact" | "comfortable" | "spacious", { panel: number; gap: number }> = {
  compact: { panel: 10, gap: 6 },
  comfortable: { panel: 14, gap: 10 },
  spacious: { panel: 18, gap: 14 },
};

const LAUNCHER_SIZE_PX: Record<"sm" | "md" | "lg", number> = {
  sm: 48,
  md: 56,
  lg: 64,
};

const LAUNCHER_RADIUS_PX_BY_SHAPE: Record<"circle" | "rounded-square" | "pill", (size: number) => number> = {
  circle: (size) => Math.floor(size / 2),
  "rounded-square": () => 14,
  pill: (size) => Math.floor(size / 2),
};

const PANEL_DIMS: Record<"sm" | "md" | "lg", { w: number; h: number }> = {
  sm: { w: 340, h: 500 },
  md: { w: 380, h: 560 },
  lg: { w: 440, h: 640 },
};

function pick<T>(value: T | null | undefined, fallback: T): T {
  return value === null || value === undefined ? fallback : value;
}

/**
 * Apply an optional dark-override layer onto a base ThemeTokens. Used
 * when buildStyles needs to emit a `.mrag-mode-dark` token block.
 */
export function applyDarkOverrides(
  base: ThemeTokens,
  overrides: WidgetDarkOverrides | null | undefined,
): ThemeTokens {
  const dark = {
    ...base,
    background: pick(overrides?.background, DEFAULT_DARK.background),
    surface: pick(overrides?.surface, DEFAULT_DARK.surface),
    foreground: pick(overrides?.foreground, DEFAULT_DARK.foreground),
    muted: pick(overrides?.muted, DEFAULT_DARK.muted),
    border: pick(overrides?.border, DEFAULT_DARK.border),
    primary: pick(overrides?.primary, base.primary),
    primaryForeground: pick(overrides?.primaryForeground, DEFAULT_DARK.primaryForeground),
  };
  return dark;
}

export function buildThemeTokens(config: WidgetConfig): ThemeTokens {
  const radius = RADIUS_PX[config.radius] ?? RADIUS_PX.md;
  const density = DENSITY_PADDING_PX[config.density] ?? DENSITY_PADDING_PX.comfortable;
  const panel = PANEL_DIMS[config.panelSize] ?? PANEL_DIMS.md;
  const launcherSizePx = LAUNCHER_SIZE_PX[config.launcherSize] ?? LAUNCHER_SIZE_PX.md;
  const launcherRadiusPx = LAUNCHER_RADIUS_PX_BY_SHAPE[config.launcherShape](launcherSizePx);

  const baseFontSizePx = SIZE_FONT_PX[config.baseFontSize] ?? SIZE_FONT_PX.md;

  const colorModeClass: ThemeTokens["colorModeClass"] =
    config.colorMode === "dark"
      ? "mrag-mode-dark"
      : config.colorMode === "auto"
        ? "mrag-mode-auto"
        : "mrag-mode-light";

  return {
    background: pick(config.background, DEFAULT_LIGHT.background),
    surface: pick(config.surface, DEFAULT_LIGHT.surface),
    foreground: pick(config.foreground, DEFAULT_LIGHT.foreground),
    muted: pick(config.muted, DEFAULT_LIGHT.muted),
    border: pick(config.border, DEFAULT_LIGHT.border),
    primary: config.primaryColor,
    primaryForeground: pick(config.primaryForeground, DEFAULT_LIGHT.primaryForeground),
    fontStack: fontStack(config.fontFamily),
    displayFontStack: config.displayFont ? fontStack(config.displayFont) : null,
    baseFontSizePx,
    radiusMessagePx: radius.msg,
    radiusPanelPx: radius.panel,
    panelPaddingPx: density.panel,
    messageGapPx: density.gap,
    panelWidthPx: panel.w,
    panelHeightPx: panel.h,
    launcherSizePx,
    launcherRadiusPx,
    colorModeClass,
  };
}
