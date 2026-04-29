import { describe, expect, it, vi } from "vitest";
import {
  _internal,
  isSafeRequestId,
  logger,
  newRequestId,
} from "../logger";

describe("redaction", () => {
  it("redacts sensitive field names", () => {
    const out = _internal.redactField("password", "hunter2");
    expect(out).toBe("[REDACTED]");
  });

  it("redacts api_key by name", () => {
    const out = _internal.redactField("api_key", "mrag_live_abc123abc123");
    expect(out).toBe("[REDACTED]");
  });

  it("redacts secret value patterns even in benign field names", () => {
    const out = _internal.redactField(
      "note",
      "see sk_live_abcdefghij1234567890 and whsec_zzzzzzzzzzzz1234",
    );
    expect(out).not.toContain("sk_live_");
    expect(out).not.toContain("whsec_");
    expect(out).toContain("[REDACTED]");
  });

  it("redacts JWT-like strings", () => {
    const out = _internal.redactField(
      "body",
      "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payloadpartcontent.signaturepart",
    );
    expect(out).toContain("[REDACTED]");
  });

  it("recursively redacts nested dicts", () => {
    const out = _internal.redactField("ctx", {
      user: { password: "hunter2", name: "Alice" },
    }) as Record<string, unknown>;
    const user = out.user as Record<string, unknown>;
    expect(user.password).toBe("[REDACTED]");
    expect(user.name).toBe("Alice");
  });

  it("scrubs values inside arrays", () => {
    const out = _internal.redactValue([
      "Bearer abc.def.ghi",
      "plain text",
    ]) as string[];
    expect(out[0]).toContain("[REDACTED]");
    expect(out[1]).toBe("plain text");
  });
});

describe("buildPayload", () => {
  it("includes ts, level, service, message", () => {
    const payload = _internal.buildPayload("info", "hello", { foo: "bar" });
    expect(payload.level).toBe("info");
    expect(payload.message).toBe("hello");
    expect(payload.service).toBe("mongorag-web");
    expect(payload.foo).toBe("bar");
    expect(payload.ts).toMatch(/^\d{4}-\d{2}-\d{2}T/);
  });

  it("redacts context fields by name", () => {
    const payload = _internal.buildPayload("info", "x", {
      password: "p",
      keep: "ok",
    });
    expect(payload.password).toBe("[REDACTED]");
    expect(payload.keep).toBe("ok");
  });
});

describe("logger.error", () => {
  it("never leaks secrets via console", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    try {
      logger.error("login_failed", {
        password: "hunter2",
        api_key: "mrag_live_abcdef",
        note: "saw sk_live_abcdefghijklmnop in logs",
      });
      const args = spy.mock.calls[0];
      const serialized = JSON.stringify(args);
      expect(serialized).not.toContain("hunter2");
      expect(serialized).not.toContain("mrag_live_abcdef");
      expect(serialized).not.toContain("sk_live_abcdefghijklmnop");
      expect(serialized).toContain("[REDACTED]");
    } finally {
      spy.mockRestore();
    }
  });
});

describe("request id", () => {
  it("mints unique ids", () => {
    const a = newRequestId();
    const b = newRequestId();
    expect(a).not.toBe(b);
    expect(a.length).toBeGreaterThanOrEqual(16);
  });

  it("treats safe ids as safe", () => {
    expect(isSafeRequestId("abc123_DEF-456")).toBe(true);
  });

  it("rejects ids with whitespace or punctuation", () => {
    expect(isSafeRequestId("abc def")).toBe(false);
    expect(isSafeRequestId("abc\ninjected")).toBe(false);
    expect(isSafeRequestId("a".repeat(100))).toBe(false);
    expect(isSafeRequestId("")).toBe(false);
  });
});
