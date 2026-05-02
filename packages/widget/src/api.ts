/**
 * Backend client for the chat widget.
 *
 * Uses fetch + ReadableStream to consume the FastAPI Server-Sent-Events
 * endpoint at POST /api/v1/chat (Accept: text/event-stream). SSE was
 * temporarily disabled while issue #84 was open — that work has merged
 * (pure ASGI middleware stack), so streaming is restored as part of #86.
 *
 * Auth: `Authorization: Bearer <apiKey>` per src/core/tenant.py.
 */

import type { SSEEvent } from "./types.js";

export interface ChatRequestBody {
  message: string;
  conversation_id?: string;
  search_type?: "hybrid" | "semantic" | "text";
}

export function buildAuthHeaders(apiKey: string): Record<string, string> {
  return {
    Authorization: `Bearer ${apiKey}`,
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };
}

export interface StreamOptions {
  apiUrl: string;
  apiKey: string;
  body: ChatRequestBody;
  signal?: AbortSignal;
}

export interface StreamResult {
  ok: boolean;
  status: number;
  events: AsyncIterable<SSEEvent>;
}

export async function startChatStream(opts: StreamOptions): Promise<StreamResult> {
  const url = `${opts.apiUrl}/api/v1/chat`;
  const response = await fetch(url, {
    method: "POST",
    headers: buildAuthHeaders(opts.apiKey),
    body: JSON.stringify(opts.body),
    credentials: "omit",
    mode: "cors",
    ...(opts.signal ? { signal: opts.signal } : {}),
  });

  if (!response.ok || !response.body) {
    return {
      ok: false,
      status: response.status,
      events: emptyAsyncIterable(),
    };
  }

  return {
    ok: true,
    status: response.status,
    events: parseSSE(response.body),
  };
}

async function* emptyAsyncIterable(): AsyncIterable<SSEEvent> {
  // Empty generator.
}

/**
 * Parse a Server-Sent-Events stream into typed events.
 *
 * Handles UTF-8 decoding, multi-line messages, and partial chunks.
 * Only supports `data:` lines; other SSE fields are ignored.
 */
export async function* parseSSE(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<SSEEvent, void, void> {
  const reader = body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let sep: number;
      // Events are separated by a blank line (\n\n).
      while ((sep = buffer.indexOf("\n\n")) !== -1) {
        const rawEvent = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        const data = extractData(rawEvent);
        if (data === null) continue;
        const parsed = tryParseJson(data);
        if (parsed) yield parsed;
      }
    }
    // Drain any final event without trailing blank line.
    const tail = buffer.trim();
    if (tail) {
      const data = extractData(tail);
      if (data !== null) {
        const parsed = tryParseJson(data);
        if (parsed) yield parsed;
      }
    }
  } finally {
    try {
      reader.releaseLock();
    } catch {
      // ignore
    }
  }
}

function extractData(rawEvent: string): string | null {
  const lines = rawEvent.split("\n");
  const dataLines: string[] = [];
  for (const line of lines) {
    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).replace(/^ /, ""));
    }
  }
  if (dataLines.length === 0) return null;
  return dataLines.join("\n");
}

function tryParseJson(text: string): SSEEvent | null {
  try {
    const parsed = JSON.parse(text);
    if (parsed && typeof parsed === "object" && typeof parsed.type === "string") {
      return parsed as SSEEvent;
    }
    return null;
  } catch {
    return null;
  }
}
