import { describe, expect, it } from "vitest";

import {
  forgotPasswordSchema,
  loginSchema,
  resetPasswordSchema,
  signupSchema,
} from "./auth";

describe("loginSchema", () => {
  it("accepts a valid email and non-empty password", () => {
    const result = loginSchema.safeParse({ email: "ok@x.io", password: "p" });
    expect(result.success).toBe(true);
  });

  it("rejects malformed emails", () => {
    const result = loginSchema.safeParse({ email: "nope", password: "p" });
    expect(result.success).toBe(false);
  });

  it("rejects empty passwords", () => {
    const result = loginSchema.safeParse({ email: "ok@x.io", password: "" });
    expect(result.success).toBe(false);
  });
});

describe("signupSchema", () => {
  it("requires password ≥ 8 chars", () => {
    const result = signupSchema.safeParse({
      email: "ok@x.io",
      password: "1234567",
      organizationName: "Acme",
    });
    expect(result.success).toBe(false);
  });

  it("rejects 1-char organization names", () => {
    const result = signupSchema.safeParse({
      email: "ok@x.io",
      password: "supersecret",
      organizationName: "A",
    });
    expect(result.success).toBe(false);
  });

  it("rejects 101-char organization names", () => {
    const result = signupSchema.safeParse({
      email: "ok@x.io",
      password: "supersecret",
      organizationName: "A".repeat(101),
    });
    expect(result.success).toBe(false);
  });

  it("accepts a valid signup payload", () => {
    const result = signupSchema.safeParse({
      email: "ok@x.io",
      password: "supersecret",
      organizationName: "Acme",
    });
    expect(result.success).toBe(true);
  });
});

describe("forgotPasswordSchema", () => {
  it("requires a valid email", () => {
    expect(forgotPasswordSchema.safeParse({ email: "x" }).success).toBe(false);
    expect(forgotPasswordSchema.safeParse({ email: "x@y.io" }).success).toBe(true);
  });
});

describe("resetPasswordSchema", () => {
  it("rejects mismatched passwords", () => {
    const result = resetPasswordSchema.safeParse({
      password: "supersecret",
      confirmPassword: "different",
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues.some((i) => i.path.includes("confirmPassword"))).toBe(true);
    }
  });

  it("accepts matching ≥8-char passwords", () => {
    const result = resetPasswordSchema.safeParse({
      password: "supersecret",
      confirmPassword: "supersecret",
    });
    expect(result.success).toBe(true);
  });
});
