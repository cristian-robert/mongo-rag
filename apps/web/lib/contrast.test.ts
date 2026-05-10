import { describe, expect, it } from "vitest";
import { contrastRatio, parseHex, wcagGrade } from "./contrast";

describe("parseHex", () => {
  it("parses 6-digit hex", () => {
    expect(parseHex("#ffffff")).toEqual({ r: 255, g: 255, b: 255 });
    expect(parseHex("#000000")).toEqual({ r: 0, g: 0, b: 0 });
    expect(parseHex("#0F172A")).toEqual({ r: 15, g: 23, b: 42 });
  });

  it("parses 8-digit hex (alpha is dropped)", () => {
    expect(parseHex("#0f172aff")).toEqual({ r: 15, g: 23, b: 42 });
  });

  it("returns null on invalid input", () => {
    expect(parseHex("0f172a")).toBeNull();
    expect(parseHex("#abc")).toBeNull();
    expect(parseHex("rgb(0,0,0)")).toBeNull();
  });
});

describe("contrastRatio", () => {
  it("white on black is 21:1", () => {
    expect(contrastRatio("#ffffff", "#000000")).toBeCloseTo(21, 1);
  });

  it("same colors is 1:1", () => {
    expect(contrastRatio("#0f172a", "#0f172a")).toBeCloseTo(1, 5);
  });

  it("white on slate-900 (#0f172a) clears AAA", () => {
    const r = contrastRatio("#ffffff", "#0f172a");
    expect(r).not.toBeNull();
    expect(r!).toBeGreaterThan(15);
  });

  it("returns null when input is not valid hex", () => {
    expect(contrastRatio("#ffffff", "not-a-color")).toBeNull();
  });
});

describe("wcagGrade", () => {
  it("normal text grading", () => {
    expect(wcagGrade(21)).toBe("AAA");
    expect(wcagGrade(7)).toBe("AAA");
    expect(wcagGrade(6.9)).toBe("AA");
    expect(wcagGrade(4.5)).toBe("AA");
    expect(wcagGrade(4.4)).toBe("AA-large");
    expect(wcagGrade(3.0)).toBe("AA-large");
    expect(wcagGrade(2.9)).toBe("fail");
  });

  it("large text grading is more lenient", () => {
    expect(wcagGrade(4.5, true)).toBe("AAA");
    expect(wcagGrade(3.0, true)).toBe("AA");
    expect(wcagGrade(2.9, true)).toBe("fail");
  });

  it("null ratio always fails", () => {
    expect(wcagGrade(null)).toBe("fail");
  });
});
