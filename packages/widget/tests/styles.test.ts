import { describe, expect, it } from "vitest";
import { buildStyles } from "../src/styles.js";
import { buildThemeTokens } from "../src/themeTokens.js";
import { baseWidgetConfig } from "./fixtures.js";

function styles(overrides = {}) {
  const cfg = baseWidgetConfig(overrides);
  return buildStyles({
    tokens: buildThemeTokens(cfg),
    darkOverrides: cfg.darkOverrides,
  });
}

describe("buildStyles", () => {
  it("emits CSS variables for the resolved theme tokens", () => {
    const css = styles();
    expect(css).toContain("--mrag-bg: #ffffff");
    expect(css).toContain("--mrag-fg: #0f172a");
    expect(css).toContain("--mrag-primary: #0f172a");
    expect(css).toContain("--mrag-launcher-size: 56px");
    expect(css).toContain("--mrag-panel-w: 380px");
  });

  it("includes a :host(.mrag-mode-dark) block with dark tokens", () => {
    const css = styles({ colorMode: "dark" });
    expect(css).toContain(":host(.mrag-mode-dark)");
    expect(css).toMatch(/:host\(\.mrag-mode-dark\)\s*\{[^}]*--mrag-bg: #0a0a0c/);
  });

  it("includes a prefers-color-scheme:dark + auto block", () => {
    const css = styles({ colorMode: "auto" });
    expect(css).toContain("@media (prefers-color-scheme: dark)");
    expect(css).toContain(":host(.mrag-mode-auto)");
  });

  it("uses the configured font stack in the host font-family", () => {
    const interCss = styles({ fontFamily: "inter" });
    expect(interCss).toMatch(/--mrag-font: Inter/);

    const systemCss = styles({ fontFamily: "system" });
    expect(systemCss).toMatch(/--mrag-font: ui-sans-serif/);
  });

  it("display-font defaults to body font when not set", () => {
    const css = styles({ fontFamily: "geist" });
    // --mrag-display-font and --mrag-font should match
    const displayMatch = css.match(/--mrag-display-font:\s*([^;]+);/);
    const fontMatch = css.match(/--mrag-font:\s*([^;]+);/);
    expect(displayMatch?.[1]).toBe(fontMatch?.[1]);
  });

  it("respects explicit dark_overrides on the dark block", () => {
    const cfg = baseWidgetConfig({
      colorMode: "dark",
      darkOverrides: { background: "#1a0033", foreground: "#fff0aa" },
    });
    const css = buildStyles({
      tokens: buildThemeTokens(cfg),
      darkOverrides: cfg.darkOverrides,
    });
    expect(css).toContain("#1a0033");
    expect(css).toContain("#fff0aa");
  });

  it("emits launcher radius reflecting the chosen shape", () => {
    const circleCss = styles({ launcherShape: "circle", launcherSize: "lg" });
    expect(circleCss).toMatch(/--mrag-launcher-radius: 32px/);

    const squareCss = styles({ launcherShape: "rounded-square", launcherSize: "lg" });
    expect(squareCss).toMatch(/--mrag-launcher-radius: 14px/);
  });

  it("preserves anti-slop asymmetric chat-bubble corners", () => {
    const css = styles();
    expect(css).toContain("border-bottom-right-radius: 4px"); // user msg
    expect(css).toContain("border-bottom-left-radius: 4px"); // assistant msg
  });

  it("includes prefers-reduced-motion overrides", () => {
    const css = styles();
    expect(css).toContain("@media (prefers-reduced-motion: reduce)");
  });
});
