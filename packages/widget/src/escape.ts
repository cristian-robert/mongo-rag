/**
 * HTML and URL escaping helpers.
 *
 * The widget never renders untrusted input via innerHTML — it always uses
 * textContent. These helpers exist for audit-friendly defense-in-depth and
 * for any future feature (e.g. clickable source links) that needs to vet
 * a URL before using it as an href.
 */

const HTML_ESCAPES: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
  "/": "&#x2F;",
};

export function escapeHtml(input: string): string {
  return input.replace(/[&<>"'/]/g, (ch) => HTML_ESCAPES[ch] ?? ch);
}

const ALLOWED_SCHEMES = new Set(["http:", "https:", "mailto:"]);

/**
 * Returns the canonical absolute URL if the input uses an allowlisted scheme,
 * or null otherwise. Relative URLs are rejected because we cannot determine
 * their effective origin in a generic embed context.
 */
export function safeUrl(url: string): string | null {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return null;
  }
  if (!ALLOWED_SCHEMES.has(parsed.protocol)) return null;
  return parsed.toString();
}
