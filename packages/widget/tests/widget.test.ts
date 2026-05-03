import { describe, expect, it } from "vitest";
import { applyEvent, buildChatBody } from "../src/widget.js";
import type { ChatMessage, SSEEvent, WidgetConfig } from "../src/types.js";

import { baseWidgetConfig } from "./fixtures.js";

function baseConfig(): WidgetConfig {
  return baseWidgetConfig();
}

function makeMsg(): ChatMessage {
  return { role: "assistant", content: "", pending: true };
}

describe("applyEvent", () => {
  it("appends content for token events", () => {
    const msg = makeMsg();
    applyEvent({ type: "token", content: "Hello " } as SSEEvent, msg, () => {});
    applyEvent({ type: "token", content: "world" } as SSEEvent, msg, () => {});
    expect(msg.content).toBe("Hello world");
    expect(msg.pending).toBe(true);
  });

  it("attaches sources from a sources event", () => {
    const msg = makeMsg();
    applyEvent(
      {
        type: "sources",
        sources: [{ document_title: "Doc", heading_path: ["A"], snippet: "s" }],
      } as SSEEvent,
      msg,
      () => {},
    );
    expect(msg.sources).toHaveLength(1);
    expect(msg.sources?.[0]?.document_title).toBe("Doc");
  });

  it("clears pending and reports conversation_id on done", () => {
    const msg = makeMsg();
    let captured = "";
    applyEvent(
      { type: "done", conversation_id: "abc" } as SSEEvent,
      msg,
      (id) => (captured = id),
    );
    expect(msg.pending).toBe(false);
    expect(captured).toBe("abc");
  });

  it("uses error message when present", () => {
    const msg = makeMsg();
    applyEvent({ type: "error", message: "Boom" } as SSEEvent, msg, () => {});
    expect(msg.content).toBe("Boom");
    expect(msg.pending).toBe(false);
  });

  it("ignores token content that is not a string", () => {
    const msg = makeMsg();
    applyEvent({ type: "token", content: 42 } as unknown as SSEEvent, msg, () => {});
    expect(msg.content).toBe("");
  });

  it("safely ignores unknown event types", () => {
    const msg = makeMsg();
    applyEvent({ type: "weird" } as SSEEvent, msg, () => {});
    expect(msg.content).toBe("");
    expect(msg.pending).toBe(true);
  });
});

describe("buildChatBody", () => {
  it("includes only message when no bot_id or conversation_id", () => {
    const cfg = baseConfig();
    const body = buildChatBody(cfg, "hello", undefined);
    expect(body).toEqual({ message: "hello" });
  });

  it("includes bot_id when config.botId is set", () => {
    const cfg: WidgetConfig = { ...baseConfig(), botId: "bot_abc" };
    const body = buildChatBody(cfg, "hello", undefined);
    expect(body.bot_id).toBe("bot_abc");
  });

  it("omits bot_id when config.botId is undefined", () => {
    const cfg = baseConfig();
    const body = buildChatBody(cfg, "hello", undefined);
    expect("bot_id" in body).toBe(false);
  });

  it("includes conversation_id when provided", () => {
    const cfg: WidgetConfig = { ...baseConfig(), botId: "bot_abc" };
    const body = buildChatBody(cfg, "hello", "conv_123");
    expect(body).toEqual({
      message: "hello",
      conversation_id: "conv_123",
      bot_id: "bot_abc",
    });
  });
});
