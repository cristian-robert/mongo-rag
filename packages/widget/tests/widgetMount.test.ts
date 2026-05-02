/**
 * Tests for the public-config bootstrap path inside mountWidget.
 *
 * Uses happy-dom (auto-loaded by vitest's environment in vitest.config.ts).
 * Stubs the public fetcher via mountWidget's options seam so we never
 * exercise real network or the real DOM globally.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { mountWidget } from "../src/widget.js";
import type { WidgetConfig } from "../src/types.js";
import type { RawConfigInput } from "../src/config.js";
import type { PublicBotConfig } from "../src/publicBot.js";

function makeConfig(overrides: Partial<WidgetConfig> = {}): WidgetConfig {
  return {
    apiKey: "mrag_test",
    apiUrl: "https://api.example.test",
    primaryColor: "#0f172a",
    botName: "Initial",
    welcomeMessage: "Initial welcome",
    position: "bottom-right",
    showBranding: false,
    ...overrides,
  };
}

function publicResponse(overrides: Partial<PublicBotConfig> = {}): PublicBotConfig {
  return {
    id: "bot_abc",
    slug: "support",
    name: "Server Bot",
    welcome_message: "Server welcome",
    widget_config: {
      primary_color: "#3366ff",
      position: "bottom-left",
      avatar_url: null,
    },
    ...overrides,
  };
}

let handles: Array<{ destroy: () => void }> = [];

afterEach(() => {
  for (const h of handles) {
    try {
      h.destroy();
    } catch {
      // ignore teardown errors
    }
  }
  handles = [];
  vi.restoreAllMocks();
});

describe("mountWidget public-config bootstrap", () => {
  it("does not call the fetcher when botId is unset", async () => {
    const fetchPublic = vi.fn();
    const handle = mountWidget(makeConfig(), {
      rawInput: { apiKey: "mrag_test" },
      fetchPublic,
    });
    handles.push(handle);

    // Allow any pending microtasks to flush.
    await Promise.resolve();
    await Promise.resolve();

    expect(fetchPublic).not.toHaveBeenCalled();
  });

  it("calls the fetcher with apiUrl + botId when botId is set", async () => {
    const fetchPublic = vi.fn().mockResolvedValue(null);
    const cfg = makeConfig({ botId: "bot_abc" });
    const handle = mountWidget(cfg, {
      rawInput: { apiKey: "mrag_test", botId: "bot_abc" },
      fetchPublic,
    });
    handles.push(handle);

    // Microtask flush to let the fetch promise resolve.
    await Promise.resolve();
    await Promise.resolve();

    expect(fetchPublic).toHaveBeenCalledTimes(1);
    expect(fetchPublic).toHaveBeenCalledWith("https://api.example.test", "bot_abc");
  });

  it("invokes onConfigUpdate with merged server values when fetch resolves", async () => {
    const fetchPublic = vi.fn().mockResolvedValue(publicResponse());
    const onConfigUpdate = vi.fn();
    const cfg = makeConfig({ botId: "bot_abc" });
    const handle = mountWidget(cfg, {
      rawInput: { apiKey: "mrag_test", botId: "bot_abc" },
      fetchPublic,
      onConfigUpdate,
    });
    handles.push(handle);

    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();

    expect(onConfigUpdate).toHaveBeenCalledTimes(1);
    const updated = onConfigUpdate.mock.calls[0]![0] as WidgetConfig;
    expect(updated.botName).toBe("Server Bot");
    expect(updated.welcomeMessage).toBe("Server welcome");
    expect(updated.primaryColor).toBe("#3366ff");
    expect(updated.position).toBe("bottom-left");
  });

  it("respects data-* overrides — explicit fields win over server values", async () => {
    const fetchPublic = vi.fn().mockResolvedValue(publicResponse());
    const onConfigUpdate = vi.fn();
    const cfg = makeConfig({
      botId: "bot_abc",
      botName: "Override",
      primaryColor: "#aabbcc",
    });
    const handle = mountWidget(cfg, {
      rawInput: {
        apiKey: "mrag_test",
        botId: "bot_abc",
        botName: "Override",
        primaryColor: "#aabbcc",
      },
      fetchPublic,
      onConfigUpdate,
    });
    handles.push(handle);

    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();

    expect(onConfigUpdate).toHaveBeenCalledTimes(1);
    const updated = onConfigUpdate.mock.calls[0]![0] as WidgetConfig;
    // Overridden fields kept the data-* value.
    expect(updated.botName).toBe("Override");
    expect(updated.primaryColor).toBe("#aabbcc");
    // Non-overridden fields took the server value.
    expect(updated.welcomeMessage).toBe("Server welcome");
    expect(updated.position).toBe("bottom-left");
  });

  it("does not invoke onConfigUpdate when fetcher rejects", async () => {
    const fetchPublic = vi.fn().mockRejectedValue(new Error("boom"));
    const onConfigUpdate = vi.fn();
    const cfg = makeConfig({ botId: "bot_abc" });
    const handle = mountWidget(cfg, {
      rawInput: { apiKey: "mrag_test", botId: "bot_abc" },
      fetchPublic,
      onConfigUpdate,
    });
    handles.push(handle);

    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();

    expect(onConfigUpdate).not.toHaveBeenCalled();
    // Widget host is still mounted.
    const host = document.querySelector("[data-mongorag-widget]");
    expect(host).not.toBeNull();
  });

  it("does not invoke onConfigUpdate when fetcher returns null", async () => {
    const fetchPublic = vi.fn().mockResolvedValue(null);
    const onConfigUpdate = vi.fn();
    const cfg = makeConfig({ botId: "bot_abc" });
    const handle = mountWidget(cfg, {
      rawInput: { apiKey: "mrag_test", botId: "bot_abc" },
      fetchPublic,
      onConfigUpdate,
    });
    handles.push(handle);

    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();

    expect(onConfigUpdate).not.toHaveBeenCalled();
  });

  it("does not call fetcher when no rawInput is provided (legacy path)", async () => {
    const fetchPublic = vi.fn();
    const cfg = makeConfig({ botId: "bot_abc" });
    // No options passed — backwards-compatible mount.
    const handle = mountWidget(cfg);
    handles.push(handle);

    await Promise.resolve();
    await Promise.resolve();

    expect(fetchPublic).not.toHaveBeenCalled();
  });
});
