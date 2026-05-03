import { describe, expect, it } from "vitest";
import { applyDarkOverrides, buildThemeTokens } from "../src/themeTokens.js";
import { baseWidgetConfig } from "./fixtures.js";

describe("buildThemeTokens", () => {
  it("uses light defaults when no color overrides are set", () => {
    const tokens = buildThemeTokens(baseWidgetConfig());
    expect(tokens.background).toBe("#ffffff");
    expect(tokens.foreground).toBe("#0f172a");
    expect(tokens.colorModeClass).toBe("mrag-mode-light");
  });

  it("derives mode class from colorMode setting", () => {
    expect(buildThemeTokens(baseWidgetConfig({ colorMode: "dark" })).colorModeClass).toBe(
      "mrag-mode-dark",
    );
    expect(buildThemeTokens(baseWidgetConfig({ colorMode: "auto" })).colorModeClass).toBe(
      "mrag-mode-auto",
    );
  });

  it("respects explicit color overrides", () => {
    const tokens = buildThemeTokens(
      baseWidgetConfig({
        background: "#101012",
        foreground: "#f5f5f7",
        primaryColor: "#3366ff",
      }),
    );
    expect(tokens.background).toBe("#101012");
    expect(tokens.foreground).toBe("#f5f5f7");
    expect(tokens.primary).toBe("#3366ff");
  });

  it("maps radius tokens to pixel values", () => {
    expect(buildThemeTokens(baseWidgetConfig({ radius: "none" })).radiusMessagePx).toBe(0);
    expect(buildThemeTokens(baseWidgetConfig({ radius: "full" })).radiusMessagePx).toBe(22);
  });

  it("maps launcher size tokens to pixel diameters", () => {
    expect(buildThemeTokens(baseWidgetConfig({ launcherSize: "sm" })).launcherSizePx).toBe(48);
    expect(buildThemeTokens(baseWidgetConfig({ launcherSize: "md" })).launcherSizePx).toBe(56);
    expect(buildThemeTokens(baseWidgetConfig({ launcherSize: "lg" })).launcherSizePx).toBe(64);
  });

  it("rounded-square launcher uses fixed 14px radius regardless of size", () => {
    const sm = buildThemeTokens(
      baseWidgetConfig({ launcherShape: "rounded-square", launcherSize: "sm" }),
    );
    const lg = buildThemeTokens(
      baseWidgetConfig({ launcherShape: "rounded-square", launcherSize: "lg" }),
    );
    expect(sm.launcherRadiusPx).toBe(14);
    expect(lg.launcherRadiusPx).toBe(14);
  });

  it("circle launcher radius is half of size", () => {
    const md = buildThemeTokens(
      baseWidgetConfig({ launcherShape: "circle", launcherSize: "md" }),
    );
    expect(md.launcherRadiusPx).toBe(28);
  });

  it("panel size token maps to width/height", () => {
    expect(buildThemeTokens(baseWidgetConfig({ panelSize: "sm" })).panelWidthPx).toBe(340);
    expect(buildThemeTokens(baseWidgetConfig({ panelSize: "lg" })).panelWidthPx).toBe(440);
  });

  it("includes the chosen font stack and a display fallback", () => {
    const t = buildThemeTokens(baseWidgetConfig({ fontFamily: "inter" }));
    expect(t.fontStack).toMatch(/Inter/);
    expect(t.displayFontStack).toBeNull();

    const tWithDisplay = buildThemeTokens(
      baseWidgetConfig({ fontFamily: "inter", displayFont: "fraunces" }),
    );
    expect(tWithDisplay.displayFontStack).toMatch(/Fraunces/);
  });

  it("base font size token maps to 13/14/15 px", () => {
    expect(buildThemeTokens(baseWidgetConfig({ baseFontSize: "sm" })).baseFontSizePx).toBe(13);
    expect(buildThemeTokens(baseWidgetConfig({ baseFontSize: "md" })).baseFontSizePx).toBe(14);
    expect(buildThemeTokens(baseWidgetConfig({ baseFontSize: "lg" })).baseFontSizePx).toBe(15);
  });
});

describe("applyDarkOverrides", () => {
  it("returns dark defaults when no overrides are provided", () => {
    const base = buildThemeTokens(baseWidgetConfig());
    const dark = applyDarkOverrides(base, null);
    expect(dark.background).toBe("#0a0a0c");
    expect(dark.foreground).toBe("#f1f1f3");
    // Primary stays — it's the brand color, doesn't auto-flip.
    expect(dark.primary).toBe(base.primary);
  });

  it("respects per-token dark overrides", () => {
    const base = buildThemeTokens(baseWidgetConfig());
    const dark = applyDarkOverrides(base, {
      background: "#202020",
      foreground: "#fafafa",
    });
    expect(dark.background).toBe("#202020");
    expect(dark.foreground).toBe("#fafafa");
    expect(dark.muted).toBe("#9aa0aa"); // unset → default dark muted
  });

  it("dark primary override flips brand color", () => {
    const base = buildThemeTokens(baseWidgetConfig({ primaryColor: "#3366ff" }));
    const dark = applyDarkOverrides(base, { primary: "#a3b8ff" });
    expect(dark.primary).toBe("#a3b8ff");
  });
});
