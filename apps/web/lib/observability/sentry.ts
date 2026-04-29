/**
 * Lazy Sentry initialization.
 *
 * Off by default. Activates only when NEXT_PUBLIC_SENTRY_DSN (browser) or
 * SENTRY_DSN (server) is set AND `@sentry/nextjs` is installed.
 *
 * The SDK is loaded via dynamic import so it never bloats bundles for
 * deployments that don't use Sentry. `@sentry/nextjs` is an optional peer
 * dependency — install it explicitly when you opt in.
 */

import { logger } from "./logger";

type SentryEvent = {
  request?: {
    cookies?: unknown;
    data?: unknown;
    headers?: Record<string, string | string[] | undefined>;
  };
};

type SentryModule = {
  init: (options: {
    dsn: string;
    environment?: string;
    release?: string;
    tracesSampleRate?: number;
    sendDefaultPii?: boolean;
    beforeSend?: (event: SentryEvent) => SentryEvent | null;
  }) => void;
};

let initialized = false;

function scrubEvent(event: SentryEvent): SentryEvent {
  if (event.request) {
    delete event.request.cookies;
    delete event.request.data;
    if (event.request.headers) {
      const scrubbed: Record<string, string> = {};
      for (const [k, v] of Object.entries(event.request.headers)) {
        scrubbed[k] = /authorization|cookie|api[-_]?key|token/i.test(k)
          ? "[REDACTED]"
          : String(v);
      }
      event.request.headers = scrubbed;
    }
  }
  return event;
}

export async function initSentryIfConfigured(): Promise<boolean> {
  if (initialized) return true;
  const dsn =
    typeof window === "undefined"
      ? process.env.SENTRY_DSN
      : process.env.NEXT_PUBLIC_SENTRY_DSN;
  if (!dsn) return false;

  try {
    // Optional peer dependency — only present when the user opts in.
    const moduleName = "@sentry/nextjs";
    const Sentry = (await import(/* webpackIgnore: true */ moduleName).catch(
      () => null,
    )) as SentryModule | null;
    if (!Sentry || typeof Sentry.init !== "function") {
      logger.warn("sentry_dsn_set_but_sdk_missing", {
        hint: "pnpm add @sentry/nextjs",
      });
      return false;
    }

    Sentry.init({
      dsn,
      environment: process.env.NODE_ENV ?? "development",
      release: process.env.SENTRY_RELEASE,
      tracesSampleRate: Number(process.env.SENTRY_TRACES_SAMPLE_RATE ?? "0"),
      sendDefaultPii: false,
      beforeSend: scrubEvent,
    });
    initialized = true;
    return true;
  } catch (err) {
    logger.error("sentry_init_failed", {
      error: err instanceof Error ? err.message : String(err),
    });
    return false;
  }
}

/** Internal — exported only for tests. */
export const _internal = { scrubEvent };
