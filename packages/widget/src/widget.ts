/**
 * Widget mount + interaction loop.
 *
 * - Renders into a closed-shadow-DOM container so host CSS cannot leak in
 *   and we cannot accidentally style the host page.
 * - All untrusted text (assistant tokens, source titles, snippets, error
 *   messages) is set via textContent, never innerHTML. Static SVG icons are
 *   built with createElementNS to avoid any innerHTML usage at all.
 * - conversation_id persists per-tenant in localStorage so sessions survive
 *   page navigations.
 */

import { startChatStream, type ChatRequestBody } from "./api.js";
import { buildStyles } from "./styles.js";
import type { ChatMessage, ChatSource, SSEEvent, WidgetConfig } from "./types.js";

const STORAGE_KEY_PREFIX = "mongorag.conversation_id:";
const SVG_NS = "http://www.w3.org/2000/svg";

interface WidgetHandle {
  destroy: () => void;
}

export function mountWidget(config: WidgetConfig): WidgetHandle {
  const host = document.createElement("div");
  host.setAttribute("data-mongorag-widget", "");
  host.style.cssText = "all: initial;";
  document.body.appendChild(host);

  const root = host.attachShadow({ mode: "closed" });

  const style = document.createElement("style");
  style.textContent = buildStyles({ primaryColor: config.primaryColor });
  root.appendChild(style);

  const launcher = createLauncher(config);
  const panel = createPanel(config);
  root.appendChild(launcher);
  root.appendChild(panel.element);

  const state = {
    open: false,
    sending: false,
    messages: [] as ChatMessage[],
    abort: null as AbortController | null,
    conversationId: loadConversationId(config.apiKey),
  };

  function setOpen(open: boolean): void {
    state.open = open;
    panel.element.dataset.open = String(open);
    launcher.setAttribute("aria-expanded", String(open));
    if (open) {
      if (state.messages.length === 0) {
        state.messages.push({ role: "assistant", content: config.welcomeMessage });
        renderMessages();
      }
      requestAnimationFrame(() => panel.input.focus());
    }
  }

  function renderMessages(): void {
    panel.messages.textContent = "";
    for (const msg of state.messages) {
      panel.messages.appendChild(renderMessage(msg));
    }
    panel.messages.scrollTop = panel.messages.scrollHeight;
  }

  async function send(rawText: string): Promise<void> {
    const text = rawText.trim();
    if (!text || state.sending) return;

    state.sending = true;
    panel.send.disabled = true;
    panel.input.disabled = true;

    state.messages.push({ role: "user", content: text });
    const assistantMsg: ChatMessage = { role: "assistant", content: "", pending: true };
    state.messages.push(assistantMsg);
    renderMessages();

    const body: ChatRequestBody = { message: text };
    if (state.conversationId) body.conversation_id = state.conversationId;

    const abort = new AbortController();
    state.abort = abort;

    try {
      const result = await startChatStream({
        apiUrl: config.apiUrl,
        apiKey: config.apiKey,
        body,
        signal: abort.signal,
      });

      if (!result.ok) {
        assistantMsg.pending = false;
        assistantMsg.content = errorMessageForStatus(result.status);
        renderMessages();
        return;
      }

      let receivedToken = false;
      for await (const event of result.events) {
        applyEvent(event, assistantMsg, (id) => {
          state.conversationId = id;
          saveConversationId(config.apiKey, id);
        });
        if (event.type === "token") receivedToken = true;
        renderMessages();
      }
      if (!receivedToken && !assistantMsg.content) {
        assistantMsg.pending = false;
        assistantMsg.content = "No response received. Please try again.";
        renderMessages();
      }
    } catch (err) {
      assistantMsg.pending = false;
      assistantMsg.content =
        err instanceof DOMException && err.name === "AbortError"
          ? "Cancelled."
          : "Couldn't reach the server. Check your connection and try again.";
      renderMessages();
    } finally {
      state.sending = false;
      state.abort = null;
      panel.send.disabled = false;
      panel.input.disabled = false;
      panel.input.focus();
    }
  }

  launcher.addEventListener("click", () => setOpen(!state.open));
  panel.close.addEventListener("click", () => setOpen(false));

  panel.form.addEventListener("submit", (e) => {
    e.preventDefault();
    const value = panel.input.value;
    panel.input.value = "";
    autoresize(panel.input);
    void send(value);
  });

  panel.input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      panel.form.requestSubmit();
    }
    if (e.key === "Escape") {
      setOpen(false);
      launcher.focus();
    }
  });

  panel.input.addEventListener("input", () => autoresize(panel.input));

  return {
    destroy() {
      state.abort?.abort();
      host.remove();
    },
  };
}

function svgIcon(paths: Array<{ tag: "path" | "line"; attrs: Record<string, string> }>): SVGSVGElement {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "2");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");
  for (const p of paths) {
    const child = document.createElementNS(SVG_NS, p.tag);
    for (const [k, v] of Object.entries(p.attrs)) child.setAttribute(k, v);
    svg.appendChild(child);
  }
  return svg;
}

function createLauncher(config: WidgetConfig): HTMLButtonElement {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = `mrag-launcher mrag-pos-${config.position === "bottom-left" ? "left" : "right"}`;
  btn.setAttribute("aria-label", `Open chat with ${config.botName}`);
  btn.setAttribute("aria-haspopup", "dialog");
  btn.setAttribute("aria-expanded", "false");
  btn.appendChild(
    svgIcon([
      { tag: "path", attrs: { d: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" } },
    ]),
  );
  return btn;
}

interface PanelRefs {
  element: HTMLDivElement;
  messages: HTMLDivElement;
  form: HTMLFormElement;
  input: HTMLTextAreaElement;
  send: HTMLButtonElement;
  close: HTMLButtonElement;
}

function createPanel(config: WidgetConfig): PanelRefs {
  const el = document.createElement("div");
  el.className = `mrag-panel mrag-pos-${config.position === "bottom-left" ? "left" : "right"}`;
  el.setAttribute("role", "dialog");
  el.setAttribute("aria-label", `${config.botName} chat`);
  el.setAttribute("aria-modal", "false");

  const header = document.createElement("div");
  header.className = "mrag-header";
  const title = document.createElement("h2");
  title.textContent = config.botName;
  const close = document.createElement("button");
  close.type = "button";
  close.className = "mrag-close";
  close.setAttribute("aria-label", "Close chat");
  close.appendChild(
    svgIcon([
      { tag: "line", attrs: { x1: "18", y1: "6", x2: "6", y2: "18" } },
      { tag: "line", attrs: { x1: "6", y1: "6", x2: "18", y2: "18" } },
    ]),
  );
  header.append(title, close);

  const messages = document.createElement("div");
  messages.className = "mrag-messages";
  messages.setAttribute("role", "log");
  messages.setAttribute("aria-live", "polite");
  messages.setAttribute("aria-relevant", "additions");

  const form = document.createElement("form");
  form.className = "mrag-form";
  form.setAttribute("aria-label", "Send message");

  const input = document.createElement("textarea");
  input.className = "mrag-input";
  input.placeholder = "Type your message…";
  input.setAttribute("aria-label", "Message");
  input.rows = 1;
  input.maxLength = 2000;

  const send = document.createElement("button");
  send.type = "submit";
  send.className = "mrag-send";
  send.textContent = "Send";

  form.append(input, send);
  el.append(header, messages, form);

  if (config.showBranding) {
    const footer = document.createElement("div");
    footer.className = "mrag-footer";
    const link = document.createElement("a");
    link.href = "https://mongorag.com";
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Powered by MongoRAG";
    footer.appendChild(link);
    el.appendChild(footer);
  }

  return { element: el, messages, form, input, send, close };
}

function renderMessage(msg: ChatMessage): HTMLDivElement {
  const wrap = document.createElement("div");
  wrap.className = `mrag-msg mrag-msg-${msg.role}`;
  if (msg.pending && !msg.content) {
    const t = document.createElement("div");
    t.className = "mrag-typing";
    t.setAttribute("aria-label", "Assistant is typing");
    for (let i = 0; i < 3; i++) t.appendChild(document.createElement("span"));
    wrap.appendChild(t);
    return wrap;
  }
  const body = document.createElement("div");
  body.textContent = msg.content;
  wrap.appendChild(body);

  if (msg.role === "assistant" && msg.sources && msg.sources.length > 0) {
    wrap.appendChild(renderSources(msg.sources));
  }
  return wrap;
}

function renderSources(sources: ChatSource[]): HTMLDetailsElement {
  const details = document.createElement("details");
  details.className = "mrag-sources";
  const summary = document.createElement("summary");
  summary.textContent = `${sources.length} source${sources.length === 1 ? "" : "s"}`;
  details.appendChild(summary);

  const ul = document.createElement("ul");
  for (const src of sources.slice(0, 8)) {
    const li = document.createElement("li");
    const t = document.createElement("div");
    t.className = "mrag-src-title";
    const headingPath = Array.isArray(src.heading_path) ? src.heading_path.join(" › ") : "";
    const title = src.document_title || "Source";
    t.textContent = headingPath ? `${title} — ${headingPath}` : title;
    li.appendChild(t);

    if (src.snippet) {
      const s = document.createElement("div");
      s.className = "mrag-src-snippet";
      s.textContent = src.snippet;
      li.appendChild(s);
    }
    ul.appendChild(li);
  }
  details.appendChild(ul);
  return details;
}

export function applyEvent(
  event: SSEEvent,
  assistantMsg: ChatMessage,
  onConversationId: (id: string) => void,
): void {
  switch (event.type) {
    case "token":
      if (typeof event.content === "string") {
        assistantMsg.content += event.content;
        assistantMsg.pending = true;
      }
      break;
    case "sources":
      if (Array.isArray(event.sources)) {
        assistantMsg.sources = event.sources;
      }
      break;
    case "done":
      assistantMsg.pending = false;
      if (typeof event.conversation_id === "string" && event.conversation_id) {
        onConversationId(event.conversation_id);
      }
      break;
    case "error":
      assistantMsg.pending = false;
      assistantMsg.content =
        typeof event.message === "string" && event.message
          ? event.message
          : "Something went wrong.";
      break;
  }
}

function errorMessageForStatus(status: number): string {
  if (status === 401 || status === 403) return "Authentication failed. Check your API key.";
  if (status === 429) return "Rate limit reached. Please try again in a moment.";
  if (status === 503 || status === 502) return "The service is temporarily unavailable.";
  if (status >= 500) return "Server error. Please try again.";
  return "Something went wrong. Please try again.";
}

function loadConversationId(apiKey: string): string | undefined {
  try {
    const v = localStorage.getItem(STORAGE_KEY_PREFIX + apiKey);
    return v || undefined;
  } catch {
    return undefined;
  }
}

function saveConversationId(apiKey: string, id: string): void {
  try {
    localStorage.setItem(STORAGE_KEY_PREFIX + apiKey, id);
  } catch {
    // ignore storage errors (private mode, etc.)
  }
}

function autoresize(el: HTMLTextAreaElement): void {
  el.style.height = "auto";
  const max = 120;
  el.style.height = Math.min(el.scrollHeight, max) + "px";
}

