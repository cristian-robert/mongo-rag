import { describe, expect, it } from "vitest";
import { applyEvent } from "../src/widget.js";
import type { ChatMessage, SSEEvent } from "../src/types.js";

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
