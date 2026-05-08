import { describe, expect, it } from "vitest";
import { evaluateWarnings, type ThemeShape } from "./anti-slop-warnings";

function base(overrides: Partial<ThemeShape> = {}): ThemeShape {
  return {
    primary_color: "#3366ff",
    primary_foreground: "#ffffff",
    font_family: "geist",
    display_font: "fraunces",
    radius: "md",
    launcher_icon: "chat",
    tone: "professional",
    ...overrides,
  };
}

describe("evaluateWarnings", () => {
  it("flags pure-default theme", () => {
    const w = evaluateWarnings({
      primary_color: "#0f172a",
      font_family: "system",
      radius: "md",
    });
    expect(w.find((x) => x.id === "default-everything")).toBeDefined();
  });

  it("does not flag default theme when one knob is non-default", () => {
    const w = evaluateWarnings({
      primary_color: "#0f172a",
      font_family: "fraunces", // different font
      radius: "md",
    });
    expect(w.find((x) => x.id === "default-everything")).toBeUndefined();
  });

  it("flags Inter for both body and display", () => {
    const w = evaluateWarnings(base({ font_family: "inter", display_font: "inter" }));
    expect(w.find((x) => x.id === "inter-everywhere")).toBeDefined();
  });

  it("does not flag Inter when paired with a different display font", () => {
    const w = evaluateWarnings(
      base({ font_family: "inter", display_font: "fraunces" }),
    );
    expect(w.find((x) => x.id === "inter-everywhere")).toBeUndefined();
  });

  it("blocks unreadable primary/foreground contrast", () => {
    // Yellow on white — terrible contrast.
    const w = evaluateWarnings(
      base({ primary_color: "#ffff00", primary_foreground: "#ffffff" }),
    );
    const c = w.find((x) => x.id === "primary-contrast");
    expect(c).toBeDefined();
    expect(c!.severity).toBe("blocker");
  });

  it("does not flag good contrast", () => {
    const w = evaluateWarnings(
      base({ primary_color: "#0f172a", primary_foreground: "#ffffff" }),
    );
    expect(w.find((x) => x.id === "primary-contrast")).toBeUndefined();
  });

  it("flags sparkle icon on professional tone", () => {
    const w = evaluateWarnings(base({ launcher_icon: "sparkle", tone: "professional" }));
    expect(w.find((x) => x.id === "sparkle-on-professional")).toBeDefined();
  });

  it("does not flag sparkle on playful tone", () => {
    const w = evaluateWarnings(base({ launcher_icon: "sparkle", tone: "playful" }));
    expect(w.find((x) => x.id === "sparkle-on-professional")).toBeUndefined();
  });

  it("flags common AI purple/blue primary", () => {
    const w = evaluateWarnings(base({ primary_color: "#7c3aed" }));
    expect(w.find((x) => x.id === "ai-gradient-color")).toBeDefined();
  });
});
