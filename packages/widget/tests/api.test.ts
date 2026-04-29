import { describe, expect, it } from "vitest";
import { buildAuthHeaders, parseSSE } from "../src/api.js";

describe("buildAuthHeaders", () => {
  it("formats the bearer token and SSE accept", () => {
    const headers = buildAuthHeaders("mrag_xyz");
    expect(headers["Authorization"]).toBe("Bearer mrag_xyz");
    expect(headers["Accept"]).toBe("text/event-stream");
    expect(headers["Content-Type"]).toBe("application/json");
  });
});

function streamFromChunks(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let i = 0;
  return new ReadableStream<Uint8Array>({
    pull(controller) {
      if (i < chunks.length) {
        controller.enqueue(encoder.encode(chunks[i]!));
        i += 1;
      } else {
        controller.close();
      }
    },
  });
}

describe("parseSSE", () => {
  it("parses a single complete event", async () => {
    const stream = streamFromChunks([
      'data: {"type":"token","content":"hi"}\n\n',
    ]);
    const events = [];
    for await (const e of parseSSE(stream)) events.push(e);
    expect(events).toEqual([{ type: "token", content: "hi" }]);
  });

  it("handles events split across chunks", async () => {
    const stream = streamFromChunks([
      'data: {"type":"to',
      'ken","content":"a"}\n\ndata: {"type":"token","content":"b"}\n\n',
    ]);
    const events = [];
    for await (const e of parseSSE(stream)) events.push(e);
    expect(events.length).toBe(2);
    expect(events[0]).toEqual({ type: "token", content: "a" });
    expect(events[1]).toEqual({ type: "token", content: "b" });
  });

  it("ignores non-data lines and malformed JSON", async () => {
    const stream = streamFromChunks([
      "event: ping\n\n",
      "data: not-json\n\n",
      'data: {"type":"done","conversation_id":"c1"}\n\n',
    ]);
    const events = [];
    for await (const e of parseSSE(stream)) events.push(e);
    expect(events).toEqual([{ type: "done", conversation_id: "c1" }]);
  });

  it("rejects events without a string type", async () => {
    const stream = streamFromChunks(['data: {"foo":"bar"}\n\n']);
    const events = [];
    for await (const e of parseSSE(stream)) events.push(e);
    expect(events).toEqual([]);
  });

  it("emits a final event without trailing blank line", async () => {
    const stream = streamFromChunks(['data: {"type":"done"}']);
    const events = [];
    for await (const e of parseSSE(stream)) events.push(e);
    expect(events).toEqual([{ type: "done" }]);
  });
});
