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
import { googleFontsUrl, isReducedData } from "./fonts.js";
import { buildStyles } from "./styles.js";
import { buildThemeTokens } from "./themeTokens.js";
import {
  fetchPublicBotConfig as defaultFetchPublic,
  mergePublicConfig,
  type PublicBotConfig,
} from "./publicBot.js";
import { RevealScheduler } from "./revealScheduler.js";
import type { RawConfigInput } from "./config.js";
import type {
  ChatMessage,
  ChatSource,
  LauncherIcon,
  SSEEvent,
  WidgetConfig,
} from "./types.js";

const STORAGE_KEY_PREFIX = "mongorag.conversation_id:";
const SVG_NS = "http://www.w3.org/2000/svg";

interface WidgetHandle {
  destroy: () => void;
}

/**
 * Optional bootstrap seam. When `rawInput` and `fetchPublic` are both
 * supplied, mountWidget will fetch the public bot config and apply
 * server values for any field the embed didn't set explicitly. The
 * `onConfigUpdate` callback is fired once the merged config is live —
 * primarily used by tests to observe the merge result without poking
 * at the closed shadow root.
 */
export interface MountOptions {
  rawInput?: RawConfigInput;
  fetchPublic?: (
    apiUrl: string,
    botId: string,
    signal?: AbortSignal,
  ) => Promise<PublicBotConfig | null>;
  onConfigUpdate?: (config: WidgetConfig) => void;
}

/**
 * Build the POST /api/v1/chat request body from the live widget config.
 *
 * `bot_id` is included only when configured (so backends still operating
 * without bot resolution see exactly the same payload as before #86). The
 * server is responsible for tying the `bot_id` to the API key's tenant —
 * the widget never claims authority for tenancy.
 */
export function buildChatBody(
  config: WidgetConfig,
  message: string,
  conversationId: string | undefined,
): ChatRequestBody {
  const body: ChatRequestBody = { message };
  if (conversationId) body.conversation_id = conversationId;
  if (config.botId) body.bot_id = config.botId;
  return body;
}

export function mountWidget(config: WidgetConfig, options: MountOptions = {}): WidgetHandle {
  // Live config snapshot. Mutated in place by applyConfigUpdate so all
  // closures capture the same reference and see the latest cosmetics
  // after the public-config fetch resolves.
  let liveConfig: WidgetConfig = { ...config };

  const host = document.createElement("div");
  host.setAttribute("data-mongorag-widget", "");
  host.style.cssText = "all: initial;";
  document.body.appendChild(host);

  const root = host.attachShadow({ mode: "closed" });

  // Container element inside the shadow root that carries the color-mode
  // class so :host(.mrag-mode-dark) / :host(.mrag-mode-auto) selectors
  // resolve. The shadow root itself can't carry classes, so we use a
  // wrapping div and configure styles to apply via descendant selectors
  // OR put the class on the host element. We put it on the host —
  // :host(.x) is the documented way to select the host when it has a
  // class — host attribute mutations re-run the cascade.
  function applyColorModeClass(mode: WidgetConfig["colorMode"]): void {
    host.classList.remove("mrag-mode-light", "mrag-mode-dark", "mrag-mode-auto");
    host.classList.add(`mrag-mode-${mode}`);
  }
  applyColorModeClass(liveConfig.colorMode);

  // Font lazy-load: inject one <link rel="stylesheet"> for any non-system
  // fonts the customer picked. prefers-reduced-data skips the load.
  const fontLink = document.createElement("link");
  fontLink.rel = "stylesheet";
  function applyFontLink(c: WidgetConfig): void {
    if (isReducedData()) {
      if (fontLink.parentNode) fontLink.parentNode.removeChild(fontLink);
      return;
    }
    const keys = c.displayFont ? [c.fontFamily, c.displayFont] : [c.fontFamily];
    const url = googleFontsUrl(keys);
    if (!url) {
      if (fontLink.parentNode) fontLink.parentNode.removeChild(fontLink);
      return;
    }
    if (fontLink.href !== url) fontLink.href = url;
    if (!fontLink.parentNode) root.appendChild(fontLink);
  }
  applyFontLink(liveConfig);

  const style = document.createElement("style");
  function rebuildStyles(c: WidgetConfig): void {
    style.textContent = buildStyles({
      tokens: buildThemeTokens(c),
      darkOverrides: c.darkOverrides ?? null,
    });
  }
  rebuildStyles(liveConfig);
  root.appendChild(style);

  const launcher = createLauncher(liveConfig);
  const panel = createPanel(liveConfig);
  root.appendChild(launcher);
  root.appendChild(panel.element);

  const state = {
    open: false,
    sending: false,
    messages: [] as ChatMessage[],
    abort: null as AbortController | null,
    reveal: null as RevealScheduler | null,
    lastUserText: "",
    conversationId: loadConversationId(liveConfig.apiKey),
  };

  function cancelInFlight(): void {
    if (state.reveal) {
      state.reveal.destroy();
      state.reveal = null;
    }
    if (state.abort) {
      state.abort.abort();
      state.abort = null;
    }
  }

  function setOpen(open: boolean): void {
    state.open = open;
    panel.element.dataset.open = String(open);
    launcher.setAttribute("aria-expanded", String(open));
    if (open) {
      if (state.messages.length === 0) {
        state.messages.push({ role: "assistant", content: liveConfig.welcomeMessage });
        renderMessages();
      }
      requestAnimationFrame(() => panel.input.focus());
    } else {
      // Closing the panel mid-stream abandons the in-flight request and any
      // buffered reveal — no DOM mutations after close.
      cancelInFlight();
    }
  }

  function renderMessages(): void {
    panel.messages.textContent = "";
    for (const msg of state.messages) {
      panel.messages.appendChild(renderMessage(msg, liveConfig));
    }
    panel.messages.scrollTop = panel.messages.scrollHeight;
  }

  /**
   * Apply a fresh config to the live widget — restyle the shadow root,
   * relabel launcher + panel, swap position class, and refresh any
   * not-yet-shown welcome message. Existing user/assistant turns are
   * preserved so re-skinning never destroys conversation state.
   *
   * With the expanded theme surface, virtually any field change can
   * affect rendering — we always rebuild styles, font link, and the
   * launcher. Cheap operations; happens at most once per config update.
   */
  function applyConfigUpdate(next: WidgetConfig): void {
    const prev = liveConfig;
    liveConfig = next;

    rebuildStyles(next);
    applyColorModeClass(next.colorMode);
    applyFontLink(next);

    if (prev.botName !== next.botName) {
      panel.title.textContent = next.botName;
      panel.element.setAttribute("aria-label", `${next.botName} chat`);
    }

    // Launcher icon / shape / size / position can all change; the
    // simplest correct path is to rebuild the launcher's children.
    relauncher(launcher, next);

    if (prev.position !== next.position) {
      const oldClass = `mrag-pos-${prev.position === "bottom-left" ? "left" : "right"}`;
      const newClass = `mrag-pos-${next.position === "bottom-left" ? "left" : "right"}`;
      panel.element.classList.remove(oldClass);
      panel.element.classList.add(newClass);
    }

    // Branding footer text update.
    if (panel.brandingLink) {
      panel.brandingLink.textContent = next.brandingText ?? "Powered by MongoRAG";
    }

    // If only the seeded welcome message is in the log, refresh it too.
    if (
      prev.welcomeMessage !== next.welcomeMessage &&
      state.messages.length === 1 &&
      state.messages[0]?.role === "assistant" &&
      state.messages[0]?.content === prev.welcomeMessage
    ) {
      state.messages[0].content = next.welcomeMessage;
      renderMessages();
    } else {
      // Avatar in existing messages may need re-rendering.
      renderMessages();
    }

    options.onConfigUpdate?.(next);
  }

  async function send(rawText: string): Promise<void> {
    const text = rawText.trim();
    if (!text) return;
    // A new send always supersedes whatever is in flight. Without this,
    // a fast double-submit would leave two readers fighting over the same
    // bubble with diverging content.
    cancelInFlight();
    if (state.sending) {
      // The previous run's finally{} block hasn't fired yet — its cleanup
      // will see state.sending=true and we'd re-enter without resetting
      // the input. Guard for that.
      state.sending = false;
    }

    state.sending = true;
    state.lastUserText = text;
    panel.send.disabled = true;
    panel.input.disabled = true;

    state.messages.push({ role: "user", content: text });
    const assistantMsg: ChatMessage = { role: "assistant", content: "", pending: true };
    state.messages.push(assistantMsg);
    renderMessages();

    const body = buildChatBody(liveConfig, text, state.conversationId);

    const abort = new AbortController();
    state.abort = abort;
    const reveal = new RevealScheduler(assistantMsg, () => renderMessages());
    state.reveal = reveal;

    try {
      const result = await startChatStream({
        apiUrl: liveConfig.apiUrl,
        apiKey: liveConfig.apiKey,
        body,
        signal: abort.signal,
      });

      if (!result.ok) {
        reveal.destroy();
        applyError(assistantMsg, errorMessageForStatus(result.status));
        renderMessages();
        return;
      }

      let receivedToken = false;
      for await (const event of result.events) {
        if (abort.signal.aborted) break;
        if (event.type === "token" && typeof event.content === "string") {
          reveal.push(event.content);
          assistantMsg.pending = true;
          receivedToken = true;
          continue;
        }
        // Sources / done / error: paint everything pending first so the
        // user sees the full streamed text before citations or error
        // copy land in the same bubble.
        reveal.flushImmediate();
        applyEvent(event, assistantMsg, (id) => {
          state.conversationId = id;
          saveConversationId(liveConfig.apiKey, id);
        });
        renderMessages();
      }
      // Drain any buffered text once the stream ends without an explicit
      // 'done' event (legacy/proxy edge case).
      reveal.flushImmediate();
      if (!receivedToken && !assistantMsg.content) {
        applyError(assistantMsg, "No response received. Please try again.");
        renderMessages();
      } else if (assistantMsg.pending) {
        // No 'done' event arrived — clear pending so typing dots vanish.
        assistantMsg.pending = false;
        renderMessages();
      }
    } catch (err) {
      // Abort is silent: don't render "Cancelled." in the bubble, just
      // remove the empty pending bubble. If content was already streamed
      // before abort, keep it (better than wiping streamed work).
      if (err instanceof DOMException && err.name === "AbortError") {
        if (!assistantMsg.content) {
          // Drop the empty pending bubble entirely.
          const idx = state.messages.indexOf(assistantMsg);
          if (idx !== -1) state.messages.splice(idx, 1);
        } else {
          assistantMsg.pending = false;
        }
        renderMessages();
        return;
      }
      reveal.destroy();
      applyError(
        assistantMsg,
        "Couldn't reach the server. Check your connection and try again.",
      );
      renderMessages();
    } finally {
      state.sending = false;
      if (state.abort === abort) state.abort = null;
      if (state.reveal === reveal) state.reveal = null;
      panel.send.disabled = false;
      panel.input.disabled = false;
      panel.input.focus();
    }
  }

  function retryLast(): void {
    const text = state.lastUserText;
    if (!text) return;
    void send(text);
  }

  // Fire the public-config fetch when we have everything needed. The
  // bubble already rendered with data-* defaults, so this never blocks.
  if (liveConfig.botId && options.rawInput && (options.fetchPublic || defaultFetchPublic)) {
    const fetcher = options.fetchPublic ?? defaultFetchPublic;
    const rawInput = options.rawInput;
    fetcher(liveConfig.apiUrl, liveConfig.botId)
      .then((server) => {
        if (server === null) return;
        const merged = mergePublicConfig(liveConfig, rawInput, server);
        applyConfigUpdate(merged);
      })
      .catch(() => {
        // Silent — keep data-* defaults already on screen.
      });
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

  // Event delegation for the retry button — added to assistant error
  // bubbles by renderMessage. Lives on the messages container so we
  // don't need a separate listener per bubble (and bubbles get rebuilt
  // on every renderMessages() call).
  panel.messages.addEventListener("click", (e) => {
    const target = e.target;
    if (!(target instanceof Element)) return;
    const btn = target.closest("[data-mrag-retry]");
    if (btn) {
      e.preventDefault();
      retryLast();
    }
  });

  return {
    destroy() {
      cancelInFlight();
      host.remove();
    },
  };
}

function applyError(msg: ChatMessage, text: string): void {
  msg.pending = false;
  msg.content = text;
  msg.error = true;
}

function svgIcon(
  paths: Array<{ tag: "path" | "line" | "circle"; attrs: Record<string, string> }>,
): SVGSVGElement {
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

const ICON_GLYPHS: Record<Exclude<LauncherIcon, "custom">, () => SVGSVGElement> = {
  chat: () =>
    svgIcon([
      {
        tag: "path",
        attrs: { d: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" },
      },
    ]),
  sparkle: () =>
    svgIcon([
      { tag: "path", attrs: { d: "M12 3v18" } },
      { tag: "path", attrs: { d: "M3 12h18" } },
      { tag: "path", attrs: { d: "M5.6 5.6l12.8 12.8" } },
      { tag: "path", attrs: { d: "M18.4 5.6L5.6 18.4" } },
    ]),
  book: () =>
    svgIcon([
      { tag: "path", attrs: { d: "M4 4h12a4 4 0 0 1 4 4v12H8a4 4 0 0 1-4-4V4z" } },
      { tag: "path", attrs: { d: "M4 16a4 4 0 0 1 4-4h12" } },
    ]),
  question: () =>
    svgIcon([
      { tag: "circle", attrs: { cx: "12", cy: "12", r: "10" } },
      { tag: "path", attrs: { d: "M9.5 9a2.5 2.5 0 0 1 5 0c0 1.5-2.5 2-2.5 4" } },
      { tag: "line", attrs: { x1: "12", y1: "17", x2: "12", y2: "17.01" } },
    ]),
};

function buildLauncherIcon(config: WidgetConfig): Node {
  if (config.launcherIcon === "custom" && config.launcherIconUrl) {
    const img = document.createElement("img");
    img.src = config.launcherIconUrl;
    img.alt = "";
    img.setAttribute("aria-hidden", "true");
    img.loading = "lazy";
    img.onerror = () => {
      // Replace failed img with the default chat glyph in-place.
      const parent = img.parentNode;
      if (parent) parent.replaceChild(ICON_GLYPHS.chat(), img);
    };
    return img;
  }
  const key = config.launcherIcon === "custom" ? "chat" : config.launcherIcon;
  return ICON_GLYPHS[key]();
}

function createLauncher(config: WidgetConfig): HTMLButtonElement {
  const btn = document.createElement("button");
  btn.type = "button";
  relauncher(btn, config);
  return btn;
}

/** (Re)build the launcher's class list, aria attributes, and icon child. */
function relauncher(btn: HTMLButtonElement, config: WidgetConfig): void {
  btn.className = `mrag-launcher mrag-pos-${config.position === "bottom-left" ? "left" : "right"}`;
  btn.setAttribute("aria-label", `Open chat with ${config.botName}`);
  btn.setAttribute("aria-haspopup", "dialog");
  btn.setAttribute("aria-expanded", btn.getAttribute("aria-expanded") ?? "false");
  // Replace child contents with the (possibly updated) icon.
  while (btn.firstChild) btn.removeChild(btn.firstChild);
  btn.appendChild(buildLauncherIcon(config));
}

interface PanelRefs {
  element: HTMLDivElement;
  title: HTMLHeadingElement;
  messages: HTMLDivElement;
  form: HTMLFormElement;
  input: HTMLTextAreaElement;
  send: HTMLButtonElement;
  close: HTMLButtonElement;
  /** Optional anchor inside the branding footer; null when showBranding=false. */
  brandingLink: HTMLAnchorElement | null;
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

  let brandingLink: HTMLAnchorElement | null = null;
  if (config.showBranding) {
    const footer = document.createElement("div");
    footer.className = "mrag-footer";
    brandingLink = document.createElement("a");
    brandingLink.href = "https://mongorag.com";
    brandingLink.target = "_blank";
    brandingLink.rel = "noopener noreferrer";
    brandingLink.textContent = config.brandingText ?? "Powered by MongoRAG";
    footer.appendChild(brandingLink);
    el.appendChild(footer);
  }

  return { element: el, title, messages, form, input, send, close, brandingLink };
}

function renderMessage(msg: ChatMessage, config?: WidgetConfig): HTMLElement {
  const bubble = document.createElement("div");
  bubble.className = `mrag-msg mrag-msg-${msg.role}`;
  if (msg.error) bubble.classList.add("mrag-msg-error");

  if (msg.pending && !msg.content) {
    const t = document.createElement("div");
    t.className = "mrag-typing";
    t.setAttribute("aria-label", "Assistant is typing");
    for (let i = 0; i < 3; i++) t.appendChild(document.createElement("span"));
    bubble.appendChild(t);
  } else {
    const body = document.createElement("div");
    body.textContent = msg.content;
    bubble.appendChild(body);

    if (msg.error) {
      const retry = document.createElement("button");
      retry.type = "button";
      retry.className = "mrag-retry";
      retry.textContent = "Retry";
      retry.setAttribute("data-mrag-retry", "");
      retry.setAttribute("aria-label", "Retry the last message");
      bubble.appendChild(retry);
    }

    if (msg.role === "assistant" && msg.sources && msg.sources.length > 0) {
      bubble.appendChild(renderSources(msg.sources));
    }
  }

  // When the bot has an avatar configured and the assistant is talking,
  // wrap the bubble in a row that puts a 24x24 avatar circle next to
  // the bubble. User messages don't get an avatar (it's their own
  // page; we don't know their face).
  if (
    msg.role === "assistant" &&
    config?.showAvatarInMessages &&
    !msg.error
  ) {
    const row = document.createElement("div");
    row.className = "mrag-msg-row";
    const avatar = renderAvatar(config);
    row.append(avatar, bubble);
    return row;
  }

  return bubble;
}

function renderAvatar(config: WidgetConfig): HTMLElement {
  const wrap = document.createElement("div");
  wrap.className = "mrag-avatar";
  if (config.avatarUrl) {
    const img = document.createElement("img");
    img.src = config.avatarUrl;
    img.alt = "";
    img.loading = "lazy";
    img.setAttribute("aria-hidden", "true");
    img.onerror = () => {
      // Fall back to initial.
      const parent = img.parentNode;
      if (parent) {
        parent.removeChild(img);
        parent.appendChild(initialChar(config.botName));
      }
    };
    wrap.appendChild(img);
  } else {
    wrap.appendChild(initialChar(config.botName));
  }
  return wrap;
}

function initialChar(name: string): Text {
  const trimmed = (name ?? "").trim();
  const initial = trimmed.length > 0 ? trimmed[0]!.toUpperCase() : "?";
  return document.createTextNode(initial);
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

