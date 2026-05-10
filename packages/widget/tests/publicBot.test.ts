import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchPublicBotConfig, mergePublicConfig } from "../src/publicBot.js";
import type { RawConfigInput } from "../src/config.js";
import type { WidgetConfig } from "../src/types.js";
import type { PublicBotConfig } from "../src/publicBot.js";
import { baseWidgetConfig } from "./fixtures.js";

function baseConfig(): WidgetConfig {
  return baseWidgetConfig({ welcomeMessage: "Hi!" });
}

function publicPayload(overrides: Partial<PublicBotConfig> = {}): PublicBotConfig {
  return {
    id: "bot_abc",
    slug: "support",
    name: "Server Bot",
    welcome_message: "Welcome from server",
    widget_config: {
      primary_color: "#3366ff",
      position: "bottom-left",
      avatar_url: null,
    },
    ...overrides,
  };
}

describe("fetchPublicBotConfig", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("returns parsed config on 200", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(publicPayload()), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const result = await fetchPublicBotConfig("https://api.example.test", "bot_abc");
    expect(result).not.toBeNull();
    expect(result?.name).toBe("Server Bot");
    expect(result?.widget_config.primary_color).toBe("#3366ff");
  });

  it("hits the correct URL with cache:force-cache", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(publicPayload()), { status: 200 }),
    );
    globalThis.fetch = fetchMock;
    await fetchPublicBotConfig("https://api.example.test/", "bot_abc");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("https://api.example.test/api/v1/bots/public/bot_abc");
    expect((init as RequestInit).cache).toBe("force-cache");
  });

  it("returns null on 404", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(new Response("", { status: 404 }));
    const result = await fetchPublicBotConfig("https://api.example.test", "bot_abc");
    expect(result).toBeNull();
  });

  it("returns null on 500", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(new Response("", { status: 500 }));
    const result = await fetchPublicBotConfig("https://api.example.test", "bot_abc");
    expect(result).toBeNull();
  });

  it("returns null on network throw", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError("network failure"));
    const result = await fetchPublicBotConfig("https://api.example.test", "bot_abc");
    expect(result).toBeNull();
  });

  it("returns null when JSON shape is invalid", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ unrelated: true }), { status: 200 }),
    );
    const result = await fetchPublicBotConfig("https://api.example.test", "bot_abc");
    expect(result).toBeNull();
  });

  it("returns null when JSON parse fails", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(new Response("not json", { status: 200 }));
    const result = await fetchPublicBotConfig("https://api.example.test", "bot_abc");
    expect(result).toBeNull();
  });
});

describe("mergePublicConfig", () => {
  it("uses server values when raw input did not set the field", () => {
    const current = baseConfig();
    const raw: RawConfigInput = { apiKey: "mrag_test", botId: "bot_abc" };
    const server = publicPayload();
    const merged = mergePublicConfig(current, raw, server);
    expect(merged.botName).toBe("Server Bot");
    expect(merged.welcomeMessage).toBe("Welcome from server");
    expect(merged.primaryColor).toBe("#3366ff");
    expect(merged.position).toBe("bottom-left");
  });

  it("keeps explicit data-* overrides over server values for botName", () => {
    const current: WidgetConfig = { ...baseConfig(), botName: "Override Bot" };
    const raw: RawConfigInput = {
      apiKey: "mrag_test",
      botId: "bot_abc",
      botName: "Override Bot",
    };
    const server = publicPayload();
    const merged = mergePublicConfig(current, raw, server);
    expect(merged.botName).toBe("Override Bot");
    // Server still wins for fields not overridden.
    expect(merged.welcomeMessage).toBe("Welcome from server");
  });

  it("keeps explicit data-* overrides for primaryColor and position", () => {
    const current: WidgetConfig = {
      ...baseConfig(),
      primaryColor: "#aabbcc",
      position: "bottom-right",
    };
    const raw: RawConfigInput = {
      apiKey: "mrag_test",
      botId: "bot_abc",
      primaryColor: "#aabbcc",
      position: "bottom-right",
    };
    const server = publicPayload();
    const merged = mergePublicConfig(current, raw, server);
    expect(merged.primaryColor).toBe("#aabbcc");
    expect(merged.position).toBe("bottom-right");
  });

  it("validates server color through the same safe-color path", () => {
    const current = baseConfig();
    const raw: RawConfigInput = { apiKey: "mrag_test", botId: "bot_abc" };
    const server = publicPayload({
      widget_config: {
        primary_color: "url(javascript:alert(1))",
        position: "bottom-left",
        avatar_url: null,
      },
    });
    const merged = mergePublicConfig(current, raw, server);
    // Falls back to current value when server value fails validation.
    expect(merged.primaryColor).toBe("#0f172a");
    expect(merged.position).toBe("bottom-left");
  });

  it("validates server position through the same safe-position path", () => {
    const current = baseConfig();
    const raw: RawConfigInput = { apiKey: "mrag_test", botId: "bot_abc" };
    const server = publicPayload({
      widget_config: {
        primary_color: "#3366ff",
        position: "top-center" as never,
        avatar_url: null,
      },
    });
    const merged = mergePublicConfig(current, raw, server);
    // Falls back to current value when server position fails validation.
    expect(merged.position).toBe("bottom-right");
  });

  it("strips control characters and truncates server text fields", () => {
    const current = baseConfig();
    const raw: RawConfigInput = { apiKey: "mrag_test", botId: "bot_abc" };
    const server = publicPayload({
      name: "Bot" + String.fromCharCode(0x07) + "Name",
      welcome_message: "x".repeat(1000),
    });
    const merged = mergePublicConfig(current, raw, server);
    expect(merged.botName).toBe("BotName");
    expect(merged.welcomeMessage.length).toBeLessThanOrEqual(400);
  });
});
