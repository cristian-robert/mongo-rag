/**
 * Pure anti-slop warning evaluator.
 *
 * Mirrors the rules in `.claude/rules/frontend-antislop.md`. Returned
 * warnings are non-blocking — the dashboard surfaces them inline next
 * to the section they apply to. Customers can dismiss them per session.
 */

import { contrastRatio, wcagGrade } from "@/lib/contrast";

export type WarningSection =
  | "color"
  | "typography"
  | "shape"
  | "branding"
  | "identity";

export type WarningSeverity = "info" | "warning" | "blocker";

export interface AntiSlopWarning {
  id: string;
  section: WarningSection;
  severity: WarningSeverity;
  title: string;
  detail: string;
}

export interface ThemeShape {
  primary_color?: string;
  primary_foreground?: string | null;
  background?: string | null;
  foreground?: string | null;
  font_family?: string;
  display_font?: string | null;
  radius?: string;
  launcher_icon?: string;
  tone?: string;
  branding_text?: string | null;
  is_default_palette?: boolean;
}

const DEFAULT_PRIMARY = "#0f172a";

export function evaluateWarnings(theme: ThemeShape): AntiSlopWarning[] {
  const warnings: AntiSlopWarning[] = [];

  // Pure default detection: primary_color matches the slate-900 default,
  // font_family is system, radius is the default 14px (md). One of
  // these is fine; all of them together is the "AI slop default look".
  if (
    theme.primary_color === DEFAULT_PRIMARY &&
    (!theme.font_family || theme.font_family === "system") &&
    (!theme.radius || theme.radius === "md")
  ) {
    warnings.push({
      id: "default-everything",
      section: "color",
      severity: "info",
      title: "Looks like the default theme",
      detail:
        "Default primary, system font, default radius — that's what every other widget uses. Try a different primary color, font, or radius for something distinctive.",
    });
  }

  // Inter for both body and display reads as generic.
  if (theme.font_family === "inter" && theme.display_font === "inter") {
    warnings.push({
      id: "inter-everywhere",
      section: "typography",
      severity: "warning",
      title: "Inter for everything reads as generic",
      detail:
        "Try Fraunces or IBM Plex Sans for the display font to add a deliberate pairing.",
    });
  }

  // Insufficient contrast on primary / primary_foreground.
  if (theme.primary_color && theme.primary_foreground) {
    const ratio = contrastRatio(theme.primary_color, theme.primary_foreground);
    const grade = wcagGrade(ratio);
    if (grade === "fail" || grade === "AA-large") {
      warnings.push({
        id: "primary-contrast",
        section: "color",
        severity: "blocker",
        title: "Text on the primary color may be hard to read",
        detail:
          ratio !== null
            ? `Contrast ratio ${ratio.toFixed(2)}:1 — WCAG AA needs at least 4.5:1 for body copy. Pick a lighter or darker text color.`
            : "Could not calculate contrast — check the color values.",
      });
    }
  }

  // Sparkle launcher icon + professional tone often reads as too playful.
  if (theme.launcher_icon === "sparkle" && theme.tone === "professional") {
    warnings.push({
      id: "sparkle-on-professional",
      section: "identity",
      severity: "info",
      title: "Sparkle icon may read as too playful",
      detail:
        "Your tone is set to professional but the launcher icon is the sparkle. Consider 'chat' or 'book' for a more grounded look.",
    });
  }

  // Detect generic AI gradient pasting (oversimplified — looks for the
  // common purple-blue 6-letter prefix). The hex inputs are normalized
  // to lowercase 6 chars in the form, so this matches reliably.
  const purpleBlueRange = ["#7c3aed", "#6366f1", "#3b82f6", "#8b5cf6"];
  if (theme.primary_color && purpleBlueRange.includes(theme.primary_color.toLowerCase())) {
    warnings.push({
      id: "ai-gradient-color",
      section: "color",
      severity: "info",
      title: "Common AI-product purple/blue",
      detail:
        "These colors show up in a lot of AI launches. A single brand-specific hue makes the widget read as yours, not generic.",
    });
  }

  return warnings;
}
