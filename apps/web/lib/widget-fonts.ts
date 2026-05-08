/**
 * Dashboard-side mirror of the widget's font catalog.
 *
 * Mirrors `packages/widget/src/fonts.ts` (which mirrors the API's
 * `BOT_FONTS` Pydantic Literal). Cross-stack alignment is enforced by
 * `apps/api/tests/test_font_conformance.py`. Adding a font means
 * touching all three sources — there is no codegen.
 */

export const WIDGET_FONT_KEYS = [
  "system",
  "inter",
  "geist",
  "ibm-plex-sans",
  "work-sans",
  "fraunces",
  "jetbrains-mono",
] as const;

export type WidgetFontKey = (typeof WIDGET_FONT_KEYS)[number];

export interface WidgetFontInfo {
  label: string;
  /** Best-effort css font stack so the dashboard sample matches widget rendering. */
  stack: string;
  role: "body" | "display" | "mono";
}

export const WIDGET_FONTS: Record<WidgetFontKey, WidgetFontInfo> = {
  system: {
    label: "System",
    stack:
      'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    role: "body",
  },
  inter: {
    label: "Inter",
    stack: 'Inter, ui-sans-serif, system-ui, sans-serif',
    role: "body",
  },
  geist: {
    label: "Geist",
    stack: 'Geist, ui-sans-serif, system-ui, sans-serif',
    role: "body",
  },
  "ibm-plex-sans": {
    label: "IBM Plex Sans",
    stack: '"IBM Plex Sans", ui-sans-serif, system-ui, sans-serif',
    role: "body",
  },
  "work-sans": {
    label: "Work Sans",
    stack: '"Work Sans", ui-sans-serif, system-ui, sans-serif',
    role: "body",
  },
  fraunces: {
    label: "Fraunces",
    stack: 'Fraunces, ui-serif, Georgia, serif',
    role: "display",
  },
  "jetbrains-mono": {
    label: "JetBrains Mono",
    stack: '"JetBrains Mono", ui-monospace, SFMono-Regular, Consolas, monospace',
    role: "mono",
  },
};

/**
 * Build a Google Fonts CSS URL for the keys given. Used by the dashboard
 * preview so the side-by-side sample doesn't need a separate font load.
 */
export function googleFontsUrl(keys: ReadonlyArray<WidgetFontKey>): string | null {
  const families: string[] = [];
  for (const key of keys) {
    if (key === "system") continue;
    const spec =
      key === "inter"
        ? "Inter:wght@400;500;600"
        : key === "geist"
          ? "Geist:wght@400;500;600"
          : key === "ibm-plex-sans"
            ? "IBM+Plex+Sans:wght@400;500;600"
            : key === "work-sans"
              ? "Work+Sans:wght@400;500;600"
              : key === "fraunces"
                ? "Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600"
                : key === "jetbrains-mono"
                  ? "JetBrains+Mono:wght@400;500;600"
                  : null;
    if (spec) families.push(spec);
  }
  if (families.length === 0) return null;
  return `https://fonts.googleapis.com/css2?${families
    .map((f) => `family=${f}`)
    .join("&")}&display=swap`;
}
