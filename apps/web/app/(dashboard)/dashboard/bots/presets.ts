/**
 * Theme presets for the bot edit form. Static dashboard-side data —
 * never persisted on the server. Customers click a preset to overwrite
 * the current widget_config; a single-step undo restores prior values.
 */

import type { CreateBotFormData } from "@/lib/validations/bots";

export type ThemePresetId =
  | "default"
  | "editorial"
  | "soft-minimal"
  | "dark-mono"
  | "brutalist";

export interface ThemePreset {
  id: ThemePresetId;
  label: string;
  description: string;
  /** Subset of widget_config that the preset sets explicitly. */
  apply: Partial<CreateBotFormData["widget_config"]>;
}

export const THEME_PRESETS: ThemePreset[] = [
  {
    id: "default",
    label: "Default",
    description: "Clean slate — system font, dark slate primary, balanced corners.",
    apply: {
      primary_color: "#0f172a",
      color_mode: "light",
      background: undefined,
      surface: undefined,
      foreground: undefined,
      muted: undefined,
      border: undefined,
      primary_foreground: "#ffffff",
      font_family: "system",
      display_font: undefined,
      base_font_size: "md",
      radius: "md",
      density: "comfortable",
      launcher_shape: "circle",
      launcher_size: "md",
      panel_size: "md",
      launcher_icon: "chat",
    },
  },
  {
    id: "editorial",
    label: "Editorial",
    description: "Display serif paired with a warm sans body. Generous radius.",
    apply: {
      primary_color: "#1f2937",
      color_mode: "light",
      background: "#fbf9f4",
      surface: "#f3efea",
      foreground: "#1f2937",
      muted: "#6b6356",
      primary_foreground: "#fbf9f4",
      font_family: "geist",
      display_font: "fraunces",
      base_font_size: "md",
      radius: "lg",
      density: "comfortable",
      launcher_shape: "rounded-square",
      launcher_size: "md",
      panel_size: "md",
      launcher_icon: "book",
    },
  },
  {
    id: "soft-minimal",
    label: "Soft minimal",
    description: "IBM Plex Sans, light gray surfaces, low-contrast restraint.",
    apply: {
      primary_color: "#475569",
      color_mode: "light",
      background: "#ffffff",
      surface: "#f1f5f9",
      foreground: "#334155",
      muted: "#94a3b8",
      primary_foreground: "#ffffff",
      font_family: "ibm-plex-sans",
      display_font: undefined,
      base_font_size: "md",
      radius: "lg",
      density: "spacious",
      launcher_shape: "circle",
      launcher_size: "md",
      panel_size: "md",
      launcher_icon: "chat",
    },
  },
  {
    id: "dark-mono",
    label: "Dark mono",
    description: "Full dark mode with a single accent. JetBrains Mono throughout.",
    apply: {
      primary_color: "#a3e635",
      color_mode: "dark",
      background: "#0a0a0c",
      surface: "#16161a",
      foreground: "#f1f1f3",
      muted: "#9aa0aa",
      primary_foreground: "#0a0a0c",
      font_family: "jetbrains-mono",
      display_font: "jetbrains-mono",
      base_font_size: "sm",
      radius: "sm",
      density: "compact",
      launcher_shape: "rounded-square",
      launcher_size: "md",
      panel_size: "md",
      launcher_icon: "chat",
    },
  },
  {
    id: "brutalist",
    label: "Brutalist",
    description: "System font, sharp 0px corners, high contrast, square launcher.",
    apply: {
      primary_color: "#000000",
      color_mode: "light",
      background: "#ffffff",
      surface: "#f5f5f5",
      foreground: "#000000",
      muted: "#525252",
      border: "#000000",
      primary_foreground: "#ffffff",
      font_family: "system",
      display_font: undefined,
      base_font_size: "md",
      radius: "none",
      density: "compact",
      launcher_shape: "rounded-square",
      launcher_size: "md",
      panel_size: "md",
      launcher_icon: "chat",
    },
  },
];
