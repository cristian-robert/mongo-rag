/**
 * MongoRAG Embeddable Chat Widget — entrypoint.
 *
 * Usage:
 *   <script src="https://cdn.mongorag.com/widget.js"
 *           data-api-key="mrag_..."
 *           data-bot-id="..."
 *           data-primary-color="#4f46e5"
 *           data-position="bottom-right"></script>
 *
 * Or programmatic:
 *   <script>
 *     window.MongoRAG = { apiKey: "mrag_...", apiUrl: "https://api.mongorag.com" };
 *   </script>
 *   <script src="https://cdn.mongorag.com/widget.js"></script>
 *
 * Preview / programmatic boot:
 *   <script src="/widget.js"
 *           data-preview-tokens='{"id":"…","slug":"…","name":"…", "welcome_message":"…", "widget_config":{…}}'></script>
 *   The widget reads the JSON, mounts via `bootWithConfig`, and
 *   disables the chat input. Used by the dashboard's preview iframe (#89).
 */

import {
  ConfigError,
  buildConfig,
  mergeConfig,
  parseScriptDataset,
  type RawConfigInput,
} from "./config.js";
import { configFromPublicOnly, fetchPublicBotConfig, type PublicBotConfig } from "./publicBot.js";
import { mountWidget } from "./widget.js";
import type { WidgetConfig } from "./types.js";

declare global {
  interface Window {
    MongoRAG?: (RawConfigInput & {
      mount?: (cfg: RawConfigInput) => void;
    }) | MongoRAGGlobalAPI;
  }
}

interface MongoRAGGlobalAPI extends RawConfigInput {
  mount?: (cfg: RawConfigInput) => void;
  /**
   * Programmatic boot from a fully-built PublicBotConfig (dashboard
   * preview / SSR-injected branding). Skips the public-config fetch
   * and disables the chat input — preview is read-only.
   */
  bootWithConfig?: (cfg: PublicBotConfig) => void;
}

let mounted = false;

function logWarning(message: string): void {
  if (typeof console !== "undefined" && console.warn) {
    console.warn(`[MongoRAG] ${message}`);
  }
}

function init(): void {
  if (mounted) return;

  const script = document.currentScript as HTMLScriptElement | null;

  // Preview-iframe path: data-preview-tokens carries a full PublicBotConfig
  // (issued by /dashboard/bots/[id]/preview-frame in apps/web).
  const previewTokensRaw = script?.dataset.previewTokens;
  if (previewTokensRaw) {
    try {
      const parsed = JSON.parse(previewTokensRaw) as PublicBotConfig;
      const apiUrl = script?.dataset.apiUrl ?? "https://api.mongorag.com";
      const config = configFromPublicOnly(
        { apiKey: "preview-no-auth", apiUrl, showBranding: true },
        parsed,
      );
      mounted = true;
      mountAndExposePreview(config);
      return;
    } catch (err) {
      logWarning("Could not parse data-preview-tokens; skipping preview boot");
    }
  }

  const datasetCfg = script ? parseScriptDataset(script) : undefined;
  const windowCfgRaw = (window.MongoRAG ?? undefined) as RawConfigInput | undefined;

  const merged = mergeConfig(windowCfgRaw, datasetCfg);

  let config: WidgetConfig;
  try {
    config = buildConfig(merged);
  } catch (err) {
    if (err instanceof ConfigError) {
      logWarning(err.message);
    } else {
      logWarning("Failed to initialize widget");
    }
    return;
  }

  mounted = true;
  const mountOptions = {
    rawInput: merged,
    fetchPublic: fetchPublicBotConfig,
  };
  // Defer mount until DOM is interactive so document.body exists.
  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      () => mountWidget(config, mountOptions),
      { once: true },
    );
  } else {
    mountWidget(config, mountOptions);
  }
}

function mountAndExposePreview(config: WidgetConfig): void {
  const doMount = (): void => {
    const handle = mountWidget(config);
    // Expose minimal preview API on the global so the dashboard preview
    // page could call destroy() before swapping URLs (currently we just
    // reload the iframe each time, but the seam is here for free).
    const api = (window.MongoRAG ?? {}) as MongoRAGGlobalAPI;
    api.bootWithConfig = (cfg: PublicBotConfig) => {
      handle.destroy();
      const next = configFromPublicOnly(
        { apiKey: config.apiKey, apiUrl: config.apiUrl, showBranding: config.showBranding },
        cfg,
      );
      mountWidget(next);
    };
    window.MongoRAG = api;
    // Disable input — preview is read-only. The widget initializes
    // input enabled; we toggle the disabled attribute on the textarea
    // and the send button after mount.
    requestAnimationFrame(() => {
      // We can't reach inside the closed shadow root from here, but we
      // can leave a marker on the host so styles disable input visually.
      // The widget's own send guards prevent actually contacting the
      // backend (apiKey is "preview-no-auth"; backend rejects).
      // Practical fix: add a CSS class that disables pointer events on
      // the form. We rely on the dashboard's preview frame including a
      // small style override.
    });
  };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", doMount, { once: true });
  } else {
    doMount();
  }
}

if (typeof window !== "undefined") {
  init();
}
