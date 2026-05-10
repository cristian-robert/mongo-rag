/**
 * Curated font catalog for the embeddable widget.
 *
 * Single source of truth for the api/web/widget triple. The Pydantic
 * Literal in `apps/api/src/models/bot.py` (`BOT_FONTS`) and the
 * dashboard font picker in `apps/web/lib/widget-fonts.ts` derive their
 * options from this map. The Python conformance test
 * (`apps/api/tests/test_font_conformance.py`) asserts that the keys
 * here match the Python tuple.
 *
 * Loading strategy:
 *
 * - `system` uses the platform sans-serif stack and emits no network
 *   request.
 * - All other entries are lazy-loaded from Google Fonts via a single
 *   `<link rel="stylesheet">` injected into the widget's Shadow DOM
 *   when first needed. This keeps the widget bundle small and lets us
 *   ship typography without bundling 200KB+ of woff2 inside the IIFE.
 *   Customers who care about privacy / no-CDN should use `system`.
 *
 * - `prefers-reduced-data` skips the Google Fonts load entirely; the
 *   widget falls back to the same stack with system substitution.
 */

export const WIDGET_FONTS = {
  system: {
    label: "System",
    stack:
      'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    google: null,
    role: "body",
  },
  inter: {
    label: "Inter",
    stack:
      'Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
    google: "Inter:wght@400;500;600",
    role: "body",
  },
  geist: {
    label: "Geist",
    stack:
      'Geist, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
    google: "Geist:wght@400;500;600",
    role: "body",
  },
  "ibm-plex-sans": {
    label: "IBM Plex Sans",
    stack:
      '"IBM Plex Sans", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
    google: "IBM+Plex+Sans:wght@400;500;600",
    role: "body",
  },
  "work-sans": {
    label: "Work Sans",
    stack:
      '"Work Sans", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
    google: "Work+Sans:wght@400;500;600",
    role: "body",
  },
  fraunces: {
    label: "Fraunces",
    stack: 'Fraunces, ui-serif, "Iowan Old Style", "Times New Roman", Georgia, serif',
    google: "Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600",
    role: "display",
  },
  "jetbrains-mono": {
    label: "JetBrains Mono",
    stack:
      '"JetBrains Mono", ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace',
    google: "JetBrains+Mono:wght@400;500;600",
    role: "mono",
  },
} as const;

export type WidgetFontKey = keyof typeof WIDGET_FONTS;

export const WIDGET_FONT_KEYS: ReadonlyArray<WidgetFontKey> = Object.keys(
  WIDGET_FONTS,
) as ReadonlyArray<WidgetFontKey>;

export function fontStack(key: WidgetFontKey): string {
  return WIDGET_FONTS[key].stack;
}

export function fontLabel(key: WidgetFontKey): string {
  return WIDGET_FONTS[key].label;
}

/**
 * Build a single Google Fonts CSS URL covering the requested font keys.
 * Returns null when no remote load is needed (all keys are `system` or
 * the array is empty).
 */
export function googleFontsUrl(keys: ReadonlyArray<WidgetFontKey>): string | null {
  const families = new Set<string>();
  for (const key of keys) {
    const spec = WIDGET_FONTS[key]?.google;
    if (spec) families.add(spec);
  }
  if (families.size === 0) return null;
  const params = Array.from(families)
    .map((f) => `family=${f}`)
    .join("&");
  return `https://fonts.googleapis.com/css2?${params}&display=swap`;
}

export function isReducedData(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  try {
    return window.matchMedia("(prefers-reduced-data: reduce)").matches;
  } catch {
    return false;
  }
}
