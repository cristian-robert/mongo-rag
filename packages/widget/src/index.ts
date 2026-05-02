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
 */

import { ConfigError, buildConfig, mergeConfig, parseScriptDataset, type RawConfigInput } from "./config.js";
import { fetchPublicBotConfig } from "./publicBot.js";
import { mountWidget } from "./widget.js";
import type { WidgetConfig } from "./types.js";

declare global {
  interface Window {
    MongoRAG?: RawConfigInput & {
      mount?: (cfg: RawConfigInput) => void;
    };
  }
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

if (typeof window !== "undefined") {
  init();
}
