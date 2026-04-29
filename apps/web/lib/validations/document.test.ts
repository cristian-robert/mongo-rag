import { describe, expect, it } from "vitest";

import {
  ACCEPTED_EXTENSIONS,
  documentMetaSchema,
  isAcceptedExtension,
  MAX_UPLOAD_BYTES,
} from "./document";

describe("isAcceptedExtension", () => {
  it("accepts every documented extension regardless of case", () => {
    for (const ext of ACCEPTED_EXTENSIONS) {
      expect(isAcceptedExtension(`a.${ext}`)).toBe(true);
      expect(isAcceptedExtension(`A.${ext.toUpperCase()}`)).toBe(true);
    }
  });

  it("rejects extensions outside the allow list", () => {
    expect(isAcceptedExtension("malware.exe")).toBe(false);
    expect(isAcceptedExtension("script.js")).toBe(false);
    expect(isAcceptedExtension("photo.png")).toBe(false);
  });

  it("rejects files with no extension", () => {
    expect(isAcceptedExtension("README")).toBe(false);
  });
});

describe("MAX_UPLOAD_BYTES", () => {
  it("is exactly 50 MB", () => {
    expect(MAX_UPLOAD_BYTES).toBe(50 * 1024 * 1024);
  });
});

describe("documentMetaSchema", () => {
  it("requires a title", () => {
    const result = documentMetaSchema.safeParse({ title: "  " });
    expect(result.success).toBe(false);
  });

  it("rejects titles longer than 200 chars", () => {
    const result = documentMetaSchema.safeParse({
      title: "x".repeat(201),
    });
    expect(result.success).toBe(false);
  });

  it("accepts a title without metadata", () => {
    const result = documentMetaSchema.safeParse({ title: "Onboarding" });
    expect(result.success).toBe(true);
  });

  it("accepts valid JSON object metadata", () => {
    const result = documentMetaSchema.safeParse({
      title: "Onboarding",
      metadataJson: '{"tags":["a"]}',
    });
    expect(result.success).toBe(true);
  });

  it("rejects invalid JSON metadata", () => {
    const result = documentMetaSchema.safeParse({
      title: "Onboarding",
      metadataJson: "{not json}",
    });
    expect(result.success).toBe(false);
  });

  it("rejects JSON arrays for metadata", () => {
    const result = documentMetaSchema.safeParse({
      title: "Onboarding",
      metadataJson: "[1,2,3]",
    });
    expect(result.success).toBe(false);
  });

  it("rejects JSON primitives for metadata", () => {
    const result = documentMetaSchema.safeParse({
      title: "Onboarding",
      metadataJson: '"a string"',
    });
    expect(result.success).toBe(false);
  });
});
