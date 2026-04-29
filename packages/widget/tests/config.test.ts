import { describe, expect, it } from "vitest";
import { ConfigError, buildConfig, mergeConfig } from "../src/config.js";

describe("buildConfig", () => {
  it("returns defaults for a minimal valid input", () => {
    const cfg = buildConfig({ apiKey: "mrag_abc" });
    expect(cfg.apiKey).toBe("mrag_abc");
    expect(cfg.apiUrl).toBe("https://api.mongorag.com");
    expect(cfg.position).toBe("bottom-right");
    expect(cfg.primaryColor).toBe("#0f172a");
    expect(cfg.botName).toBe("Assistant");
    expect(cfg.showBranding).toBe(true);
  });

  it("throws when apiKey is missing", () => {
    expect(() => buildConfig({})).toThrow(ConfigError);
  });

  it("rejects an apiKey without the mrag_ prefix", () => {
    expect(() => buildConfig({ apiKey: "sk-abc" })).toThrow(/mrag_/);
  });

  it("rejects javascript: schemes for apiUrl", () => {
    expect(() => buildConfig({ apiKey: "mrag_x", apiUrl: "javascript:alert(1)" })).toThrow(
      ConfigError,
    );
  });

  it("rejects file: schemes for apiUrl", () => {
    expect(() => buildConfig({ apiKey: "mrag_x", apiUrl: "file:///etc/passwd" })).toThrow(
      ConfigError,
    );
  });

  it("strips trailing slashes from apiUrl", () => {
    const cfg = buildConfig({ apiKey: "mrag_x", apiUrl: "https://api.example.com//" });
    expect(cfg.apiUrl).toBe("https://api.example.com");
  });

  it("falls back to safe color when given an unsafe value", () => {
    const cfg = buildConfig({
      apiKey: "mrag_x",
      primaryColor: "url(javascript:alert(1))",
    });
    expect(cfg.primaryColor).toBe("#0f172a");
  });

  it("accepts a valid hex color", () => {
    const cfg = buildConfig({ apiKey: "mrag_x", primaryColor: "#ff5500" });
    expect(cfg.primaryColor).toBe("#ff5500");
  });

  it("falls back to bottom-right for an unknown position", () => {
    const cfg = buildConfig({ apiKey: "mrag_x", position: "top-center" });
    expect(cfg.position).toBe("bottom-right");
  });

  it("strips C0 control characters from text fields", () => {
    const malicious = "Bot" + String.fromCharCode(0x07) + "Name" + String.fromCharCode(0x1b);
    const cfg = buildConfig({ apiKey: "mrag_x", botName: malicious });
    expect(cfg.botName).toBe("BotName");
  });

  it("truncates excessively long text", () => {
    const long = "x".repeat(1000);
    const cfg = buildConfig({ apiKey: "mrag_x", welcomeMessage: long });
    expect(cfg.welcomeMessage.length).toBeLessThanOrEqual(400);
  });

  it("respects showBranding=false from string input", () => {
    const cfg = buildConfig({ apiKey: "mrag_x", showBranding: "false" });
    expect(cfg.showBranding).toBe(false);
  });
});

describe("mergeConfig", () => {
  it("primary overrides fallback", () => {
    const merged = mergeConfig(
      { apiKey: "mrag_a" },
      { apiKey: "mrag_b", apiUrl: "https://x.test" },
    );
    expect(merged.apiKey).toBe("mrag_a");
    expect(merged.apiUrl).toBe("https://x.test");
  });

  it("handles undefined inputs", () => {
    expect(mergeConfig(undefined, undefined)).toEqual({});
  });
});
