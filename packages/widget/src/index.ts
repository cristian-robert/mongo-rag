/**
 * MongoRAG Embeddable Chat Widget
 *
 * Usage:
 *   <script src="https://cdn.mongorag.com/widget.js"
 *           data-api-key="mrag_..." />
 */

interface MongoRAGConfig {
  apiKey: string;
  apiUrl?: string;
}

function init(): void {
  const script = document.currentScript as HTMLScriptElement | null;
  if (!script) return;

  const config: MongoRAGConfig = {
    apiKey: script.dataset.apiKey || "",
    apiUrl: script.dataset.apiUrl || "",
  };

  if (!config.apiKey) {
    console.warn("[MongoRAG] Missing data-api-key attribute");
    return;
  }

  console.log("[MongoRAG] Widget initialized", { apiUrl: config.apiUrl });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
