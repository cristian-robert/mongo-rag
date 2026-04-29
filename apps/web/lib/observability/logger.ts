/**
 * Structured logger for the Next.js app.
 *
 * - Server-side: emits one-line JSON to stdout in production, pretty in dev.
 * - Client-side: forwards through console with the same shape.
 * - Redacts secret-looking field names AND value patterns before any sink.
 *
 * Zero runtime dependencies — keeps bundle size tiny on the client.
 */

const SENSITIVE_KEY_RE =
  /(password|passwd|secret|token|api[_-]?key|authorization|cookie|session|stripe|webhook|signing|bearer|client[_-]?secret|private[_-]?key)/i;

const SECRET_VALUE_RES: RegExp[] = [
  /sk_(?:live|test)_[A-Za-z0-9]{16,}/g,
  /whsec_[A-Za-z0-9]{16,}/g,
  /sb_(?:secret|publishable)_[A-Za-z0-9]{16,}/g,
  /Bearer\s+[A-Za-z0-9._-]+/gi,
  /eyJ[A-Za-z0-9._-]{20,}/g,
];

const REDACTED = "[REDACTED]";

export type LogLevel = "debug" | "info" | "warn" | "error";

export interface LogContext {
  request_id?: string;
  tenant_id?: string;
  user_id?: string;
  [key: string]: unknown;
}

interface LogPayload extends LogContext {
  ts: string;
  level: LogLevel;
  service: string;
  message: string;
}

function redactValue(value: unknown): unknown {
  if (typeof value === "string") {
    let scrubbed = value;
    for (const re of SECRET_VALUE_RES) {
      scrubbed = scrubbed.replace(re, REDACTED);
    }
    return scrubbed;
  }
  if (Array.isArray(value)) {
    return value.map(redactValue);
  }
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      out[k] = redactField(k, v);
    }
    return out;
  }
  return value;
}

function redactField(key: string, value: unknown): unknown {
  if (SENSITIVE_KEY_RE.test(key)) {
    return REDACTED;
  }
  return redactValue(value);
}

function buildPayload(
  level: LogLevel,
  message: string,
  context: LogContext = {},
  service = "mongorag-web",
): LogPayload {
  const sanitized: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(context)) {
    sanitized[k] = redactField(k, v);
  }
  return {
    ts: new Date().toISOString(),
    level,
    service,
    message,
    ...sanitized,
  } as LogPayload;
}

const isProd = process.env.NODE_ENV === "production";
const isServer = typeof window === "undefined";

function emit(payload: LogPayload): void {
  const line = JSON.stringify(payload);
  if (isServer && isProd) {
    process.stdout.write(`${line}\n`);
    return;
  }
  // Dev or browser — go through console so the browser tools / next dev format render nicely.
  const sink =
    payload.level === "error"
      ? console.error
      : payload.level === "warn"
        ? console.warn
        : payload.level === "debug"
          ? console.debug
          : console.info;
  if (isProd) {
    sink(line);
  } else {
    sink(`[${payload.level}] ${payload.message}`, payload);
  }
}

export const logger = {
  debug(message: string, context?: LogContext) {
    emit(buildPayload("debug", message, context));
  },
  info(message: string, context?: LogContext) {
    emit(buildPayload("info", message, context));
  },
  warn(message: string, context?: LogContext) {
    emit(buildPayload("warn", message, context));
  },
  error(message: string, context?: LogContext) {
    emit(buildPayload("error", message, context));
  },
};

/** Generate a fresh request_id (UUIDv4). */
export function newRequestId(): string {
  // Browsers and modern Node both support crypto.randomUUID
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID().replace(/-/g, "");
  }
  // Fallback — RFC 4122 v4 from Math.random (only ever hit in ancient runtimes).
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

export const REQUEST_ID_HEADER = "x-request-id";

/** Internal — exported only for tests. */
export const _internal = { redactField, redactValue, buildPayload };
