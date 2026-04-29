/**
 * Edge-runtime-safe helpers for the per-request request_id.
 *
 * Kept in a standalone module so middleware (Edge) can import them without
 * pulling in the Node.js logger sink (`process.stdout.write`).
 */

export const REQUEST_ID_HEADER = "x-request-id";

/** Generate a fresh request_id (32 hex chars, no dashes). */
export function newRequestId(): string {
  // Browsers, Edge, and modern Node all support crypto.randomUUID.
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID().replace(/-/g, "");
  }
  // Fallback — RFC 4122 v4 from Math.random (only hit in ancient runtimes).
  return "xxxxxxxxxxxx4xxxyxxxxxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/** Validate a request_id is safe to forward upstream (no log injection). */
export function isSafeRequestId(value: string): boolean {
  if (!value || value.length > 64) return false;
  return /^[A-Za-z0-9_-]+$/.test(value);
}
