/**
 * Token-driven scoped CSS for the widget. Returned as a string and
 * inserted via a single <style> element inside the Shadow DOM, so it
 * cannot leak into the host page.
 *
 * Source of theme values: `ThemeTokens` derived from `WidgetConfig`.
 *
 * Anti-AI-slop guardrails (preserved from the previous styles):
 *   - No purple→blue gradient on launcher / send button — solid primary only.
 *   - Asymmetric chat-bubble corners (border-bottom-{right,left}-radius: 4px)
 *     to keep the look intentional, not generic-rounded-rectangle.
 *   - Custom 1px borders instead of default shadcn-style glow.
 *   - Motion respects prefers-reduced-motion.
 */

import type { WidgetDarkOverrides } from "./types.js";
import { applyDarkOverrides, type ThemeTokens } from "./themeTokens.js";

export interface BuildStylesOptions {
  tokens: ThemeTokens;
  /** Dark-mode override layer. When null/undefined we synthesize defaults. */
  darkOverrides?: WidgetDarkOverrides | null;
}

export function buildStyles(opts: BuildStylesOptions): string {
  const t = opts.tokens;
  const dark = applyDarkOverrides(t, opts.darkOverrides);

  const display = t.displayFontStack ?? t.fontStack;

  return `
:host {
  --mrag-bg: ${t.background};
  --mrag-surface: ${t.surface};
  --mrag-fg: ${t.foreground};
  --mrag-muted: ${t.muted};
  --mrag-border: ${t.border};
  --mrag-primary: ${t.primary};
  --mrag-primary-fg: ${t.primaryForeground};
  --mrag-radius-msg: ${t.radiusMessagePx}px;
  --mrag-radius-panel: ${t.radiusPanelPx}px;
  --mrag-launcher-size: ${t.launcherSizePx}px;
  --mrag-launcher-radius: ${t.launcherRadiusPx}px;
  --mrag-panel-w: ${t.panelWidthPx}px;
  --mrag-panel-h: ${t.panelHeightPx}px;
  --mrag-pad: ${t.panelPaddingPx}px;
  --mrag-gap: ${t.messageGapPx}px;
  --mrag-fs: ${t.baseFontSizePx}px;
  --mrag-font: ${t.fontStack};
  --mrag-display-font: ${display};

  all: initial;
  font-family: var(--mrag-font);
  color: var(--mrag-fg);
  font-size: var(--mrag-fs);
  line-height: 1.5;
}

/* Explicit dark mode (color_mode = "dark"). Tokens already point at the
 * dark palette via :host above (set by buildThemeTokens caller), but we
 * also expose this class so :host(.mrag-mode-dark) consumers can target
 * dark-only rules if needed. */
:host(.mrag-mode-dark) {
  --mrag-bg: ${dark.background};
  --mrag-surface: ${dark.surface};
  --mrag-fg: ${dark.foreground};
  --mrag-muted: ${dark.muted};
  --mrag-border: ${dark.border};
  --mrag-primary: ${dark.primary};
  --mrag-primary-fg: ${dark.primaryForeground};
}

/* Auto: follow the host page's prefers-color-scheme. */
@media (prefers-color-scheme: dark) {
  :host(.mrag-mode-auto) {
    --mrag-bg: ${dark.background};
    --mrag-surface: ${dark.surface};
    --mrag-fg: ${dark.foreground};
    --mrag-muted: ${dark.muted};
    --mrag-border: ${dark.border};
    --mrag-primary: ${dark.primary};
    --mrag-primary-fg: ${dark.primaryForeground};
  }
}

* {
  box-sizing: border-box;
}

.mrag-launcher {
  position: fixed;
  bottom: 20px;
  width: var(--mrag-launcher-size);
  height: var(--mrag-launcher-size);
  border-radius: var(--mrag-launcher-radius);
  border: none;
  background: var(--mrag-primary);
  color: var(--mrag-primary-fg);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.18);
  z-index: 2147483646;
  transition: transform 160ms ease;
  overflow: hidden;
}
.mrag-launcher:hover { transform: translateY(-1px); }
.mrag-launcher:focus-visible {
  outline: 2px solid var(--mrag-primary);
  outline-offset: 3px;
}
.mrag-launcher svg { width: 24px; height: 24px; }
.mrag-launcher img {
  width: 60%;
  height: 60%;
  object-fit: contain;
}

.mrag-pos-right { right: 20px; }
.mrag-pos-left  { left: 20px; }

.mrag-panel {
  position: fixed;
  bottom: calc(var(--mrag-launcher-size) + 30px);
  width: var(--mrag-panel-w);
  max-width: calc(100vw - 24px);
  height: var(--mrag-panel-h);
  max-height: calc(100vh - 110px);
  background: var(--mrag-bg);
  border: 1px solid var(--mrag-border);
  border-radius: var(--mrag-radius-panel);
  box-shadow: 0 20px 60px rgba(15, 23, 42, 0.16);
  display: none;
  flex-direction: column;
  overflow: hidden;
  z-index: 2147483647;
}
.mrag-panel[data-open="true"] { display: flex; }

.mrag-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid var(--mrag-border);
  background: var(--mrag-primary);
  color: var(--mrag-primary-fg);
}
.mrag-header h2 {
  font-family: var(--mrag-display-font);
  font-size: 14px;
  font-weight: 600;
  margin: 0;
  letter-spacing: -0.01em;
}
.mrag-close {
  background: transparent;
  border: 0;
  color: var(--mrag-primary-fg);
  cursor: pointer;
  padding: 4px;
  border-radius: 6px;
  line-height: 0;
}
.mrag-close:hover { background: rgba(255, 255, 255, 0.15); }
.mrag-close:focus-visible { outline: 2px solid currentColor; outline-offset: 1px; }

.mrag-messages {
  flex: 1 1 auto;
  overflow-y: auto;
  padding: var(--mrag-pad);
  display: flex;
  flex-direction: column;
  gap: var(--mrag-gap);
  background: var(--mrag-surface);
}

.mrag-msg-row {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}
.mrag-msg-row.is-user {
  flex-direction: row-reverse;
}

.mrag-avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  flex-shrink: 0;
  overflow: hidden;
  background: var(--mrag-primary);
  color: var(--mrag-primary-fg);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
}
.mrag-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.mrag-msg {
  max-width: 85%;
  padding: 9px 12px;
  border-radius: var(--mrag-radius-msg);
  word-wrap: break-word;
  white-space: pre-wrap;
  font-size: var(--mrag-fs);
}
.mrag-msg-user {
  align-self: flex-end;
  background: var(--mrag-primary);
  color: var(--mrag-primary-fg);
  border-bottom-right-radius: 4px;
}
.mrag-msg-assistant {
  align-self: flex-start;
  background: var(--mrag-bg);
  border: 1px solid var(--mrag-border);
  border-bottom-left-radius: 4px;
}
.mrag-msg-system {
  align-self: center;
  background: transparent;
  color: var(--mrag-muted);
  font-size: 12px;
  font-style: italic;
}
.mrag-msg-error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
}
.mrag-retry {
  display: inline-flex;
  align-items: center;
  margin-top: 6px;
  padding: 4px 10px;
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  background: #fff;
  color: #991b1b;
  border: 1px solid #fecaca;
  border-radius: 8px;
  cursor: pointer;
  transition: background 120ms ease;
}
.mrag-retry:hover { background: #fef2f2; }
.mrag-retry:focus-visible {
  outline: 2px solid #991b1b;
  outline-offset: 2px;
}

.mrag-typing {
  display: inline-flex;
  gap: 4px;
  padding: 6px 0;
}
.mrag-typing span {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--mrag-muted);
  animation: mrag-bounce 1.2s infinite ease-in-out;
}
.mrag-typing span:nth-child(2) { animation-delay: 0.15s; }
.mrag-typing span:nth-child(3) { animation-delay: 0.3s; }

@keyframes mrag-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.5; }
  30% { transform: translateY(-4px); opacity: 1; }
}

@media (prefers-reduced-motion: reduce) {
  .mrag-launcher { transition: none; }
  .mrag-typing span { animation: none; opacity: 0.7; }
  .mrag-retry { transition: none; }
}

.mrag-sources {
  margin-top: 6px;
  font-size: 12px;
}
.mrag-sources summary {
  cursor: pointer;
  color: var(--mrag-muted);
  user-select: none;
}
.mrag-sources summary:hover { color: var(--mrag-fg); }
.mrag-sources ul {
  list-style: none;
  margin: 6px 0 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.mrag-sources li {
  background: var(--mrag-surface);
  border: 1px solid var(--mrag-border);
  border-radius: 8px;
  padding: 6px 8px;
}
.mrag-sources .mrag-src-title {
  font-weight: 600;
  font-size: 12px;
}
.mrag-sources .mrag-src-snippet {
  color: var(--mrag-muted);
  font-size: 11px;
  margin-top: 2px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.mrag-form {
  display: flex;
  gap: 8px;
  padding: 10px;
  border-top: 1px solid var(--mrag-border);
  background: var(--mrag-bg);
}
.mrag-input {
  flex: 1;
  padding: 9px 12px;
  font: inherit;
  color: inherit;
  background: var(--mrag-surface);
  border: 1px solid var(--mrag-border);
  border-radius: 10px;
  outline: none;
  resize: none;
  max-height: 120px;
  min-height: 38px;
}
.mrag-input:focus {
  border-color: var(--mrag-primary);
  box-shadow: 0 0 0 3px rgba(15, 23, 42, 0.06);
}
.mrag-input:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}
.mrag-send {
  background: var(--mrag-primary);
  color: var(--mrag-primary-fg);
  border: 0;
  border-radius: 10px;
  padding: 0 14px;
  cursor: pointer;
  font: inherit;
  font-weight: 600;
}
.mrag-send:disabled { opacity: 0.5; cursor: not-allowed; }
.mrag-send:focus-visible { outline: 2px solid var(--mrag-primary); outline-offset: 2px; }

.mrag-footer {
  text-align: center;
  font-size: 11px;
  color: var(--mrag-muted);
  padding: 6px 0 8px 0;
  border-top: 1px solid var(--mrag-border);
  background: var(--mrag-bg);
}
.mrag-footer a {
  color: var(--mrag-muted);
  text-decoration: none;
}
.mrag-footer a:hover { text-decoration: underline; }

.mrag-error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 12px;
  margin: 8px 14px;
}

@media (max-width: 480px) {
  .mrag-panel {
    width: calc(100vw - 16px);
    height: calc(100vh - 100px);
    bottom: calc(var(--mrag-launcher-size) + 24px);
  }
  .mrag-pos-right { right: 8px; }
  .mrag-pos-left  { left: 8px; }
}
`;
}
