import { describe, expect, it } from "vitest";

import {
  createBotSchema,
  defaultBotFormValues,
  updateBotSchema,
} from "./bots";

const VALID = {
  ...defaultBotFormValues,
  name: "Support Bot",
  slug: "support-bot",
};

describe("createBotSchema", () => {
  it("accepts a fully valid payload", () => {
    const result = createBotSchema.safeParse(VALID);
    expect(result.success).toBe(true);
  });

  it("rejects slugs with uppercase or symbols", () => {
    expect(
      createBotSchema.safeParse({ ...VALID, slug: "Support Bot!" }).success,
    ).toBe(false);
    expect(
      createBotSchema.safeParse({ ...VALID, slug: "-leading" }).success,
    ).toBe(false);
    expect(
      createBotSchema.safeParse({ ...VALID, slug: "trailing-" }).success,
    ).toBe(false);
  });

  it("requires a system prompt of at least 10 characters", () => {
    const result = createBotSchema.safeParse({
      ...VALID,
      system_prompt: "short",
    });
    expect(result.success).toBe(false);
  });

  it("rejects out-of-range temperature", () => {
    expect(
      createBotSchema.safeParse({
        ...VALID,
        model_config: { temperature: 1.5, max_tokens: 1024 },
      }).success,
    ).toBe(false);
  });

  it("rejects non-https avatar URLs", () => {
    expect(
      createBotSchema.safeParse({
        ...VALID,
        widget_config: {
          ...VALID.widget_config,
          avatar_url: "http://insecure.example/img.png",
        },
      }).success,
    ).toBe(false);
  });

  it("rejects non-hex primary colors", () => {
    expect(
      createBotSchema.safeParse({
        ...VALID,
        widget_config: { ...VALID.widget_config, primary_color: "blue" },
      }).success,
    ).toBe(false);
  });

  it("normalizes slug to lowercase", () => {
    const result = createBotSchema.safeParse({ ...VALID, slug: "MIXED-case" });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.slug).toBe("mixed-case");
    }
  });
});

describe("updateBotSchema", () => {
  it("strips slug field if provided (immutable post-create)", () => {
    const result = updateBotSchema.safeParse({
      name: "Updated",
      slug: "different-slug",
    });
    // Slug is `omit`ed; extra keys are stripped silently, parse should succeed
    // but result.data must not contain slug.
    expect(result.success).toBe(true);
    if (result.success) {
      expect("slug" in result.data).toBe(false);
    }
  });

  it("accepts a partial update", () => {
    const result = updateBotSchema.safeParse({ name: "Renamed" });
    expect(result.success).toBe(true);
  });
});
