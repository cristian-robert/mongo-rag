import { describe, expect, it } from "vitest";
import { escapeHtml, safeUrl } from "../src/escape.js";

describe("escapeHtml", () => {
  it("escapes the standard HTML metacharacters", () => {
    expect(escapeHtml('<script>alert("x")</script>')).toBe(
      "&lt;script&gt;alert(&quot;x&quot;)&lt;&#x2F;script&gt;",
    );
  });

  it("escapes ampersands first to avoid double-encoding", () => {
    expect(escapeHtml("a & b")).toBe("a &amp; b");
  });

  it("escapes single quotes", () => {
    expect(escapeHtml("it's")).toBe("it&#39;s");
  });
});

describe("safeUrl", () => {
  it("accepts https URLs", () => {
    expect(safeUrl("https://example.com")).toBe("https://example.com/");
  });

  it("accepts http URLs", () => {
    expect(safeUrl("http://example.com/page")).toBe("http://example.com/page");
  });

  it("rejects javascript: URLs", () => {
    expect(safeUrl("javascript:alert(1)")).toBeNull();
  });

  it("rejects data: URLs", () => {
    expect(safeUrl("data:text/html,<script>alert(1)</script>")).toBeNull();
  });

  it("rejects relative paths (no scheme)", () => {
    expect(safeUrl("/foo/bar")).toBeNull();
  });
});
