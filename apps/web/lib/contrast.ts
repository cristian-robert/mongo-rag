/**
 * WCAG contrast helpers.
 *
 * Used by the bot-form theme controls to surface a small AA/AAA badge
 * next to color pairs (primary / primary_foreground, foreground /
 * background, etc.) so customers don't ship illegible widgets.
 *
 * Only the basic relative-luminance algorithm — no APCA, no
 * gamma-corrected color spaces. Matches what most contrast pickers
 * report.
 */

const HEX_RE = /^#([0-9a-f]{6})([0-9a-f]{2})?$/i;

export interface RGB {
  r: number;
  g: number;
  b: number;
}

export function parseHex(hex: string): RGB | null {
  const m = hex.match(HEX_RE);
  if (!m) return null;
  const main = m[1]!;
  return {
    r: parseInt(main.slice(0, 2), 16),
    g: parseInt(main.slice(2, 4), 16),
    b: parseInt(main.slice(4, 6), 16),
  };
}

function srgbChannel(c: number): number {
  const v = c / 255;
  return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
}

export function relativeLuminance({ r, g, b }: RGB): number {
  return 0.2126 * srgbChannel(r) + 0.7152 * srgbChannel(g) + 0.0722 * srgbChannel(b);
}

/**
 * WCAG contrast ratio between two colors. Returns the canonical
 * 1.0–21.0 ratio. Returns null when either input is not a valid #RRGGBB
 * hex.
 */
export function contrastRatio(a: string, b: string): number | null {
  const ca = parseHex(a);
  const cb = parseHex(b);
  if (!ca || !cb) return null;
  const la = relativeLuminance(ca);
  const lb = relativeLuminance(cb);
  const lighter = Math.max(la, lb);
  const darker = Math.min(la, lb);
  return (lighter + 0.05) / (darker + 0.05);
}

export type WCAGGrade = "AAA" | "AA" | "AA-large" | "fail";

/**
 * Map a contrast ratio to a WCAG grade. `largeText` lowers the bars
 * (4.5 → 3.0 for AA, 7 → 4.5 for AAA).
 */
export function wcagGrade(ratio: number | null, largeText = false): WCAGGrade {
  if (ratio === null) return "fail";
  if (largeText) {
    if (ratio >= 4.5) return "AAA";
    if (ratio >= 3.0) return "AA";
    return "fail";
  }
  if (ratio >= 7.0) return "AAA";
  if (ratio >= 4.5) return "AA";
  if (ratio >= 3.0) return "AA-large";
  return "fail";
}
