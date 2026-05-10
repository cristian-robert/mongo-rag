import { NextResponse, type NextRequest } from "next/server";

import {
  REQUEST_ID_HEADER,
  isSafeRequestId,
  newRequestId,
} from "@/lib/observability/request-id";
import { updateSession } from "@/lib/supabase/middleware";

const authRoutes = ["/login", "/signup", "/forgot-password", "/reset-password"];

// Marketing routes are public and never trigger auth redirects.
const marketingRoutes = ["/", "/pricing"];

// Public path prefixes — accessible without auth, no auto-redirect either way.
const publicRoutePrefixes = ["/invite/"];

const isProd = process.env.NODE_ENV === "production";
const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8100";
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;

const apiOrigin = (() => {
  try {
    return new URL(apiUrl).origin;
  } catch {
    return "http://localhost:8100";
  }
})();

const supabaseOrigin = (() => {
  if (!supabaseUrl) return null;
  try {
    return new URL(supabaseUrl).origin;
  } catch {
    return null;
  }
})();

const supabaseConnectSrc = supabaseOrigin
  ? [supabaseOrigin, supabaseOrigin.replace(/^https/, "wss")]
  : [];

function generateNonce(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

/**
 * Per-request CSP. Next.js 16 inlines its hydration payload as
 * `<script>self.__next_f.push(...)</script>` blocks; without `'nonce-X'`
 * + `'strict-dynamic'` the browser silently drops every inline tag and
 * the page never hydrates (blank screen). The nonce is also exposed via
 * the `x-nonce` request header so Next.js auto-applies it to every
 * `<script>` and `<link rel="preload" as="script">` it emits.
 */
// Routes that may be embedded in a same-origin iframe (e.g. the bot preview
// pane on the bot edit page). Default for everything else stays strict
// `frame-ancestors 'none'` — a clickjacking-resistant baseline.
function allowsSelfFraming(pathname: string): boolean {
  return /^\/dashboard\/bots\/[^/]+\/preview-frame\/?$/.test(pathname);
}

function buildCsp(nonce: string, pathname: string): string {
  const scriptSrc = isProd
    ? [`'nonce-${nonce}'`, "'strict-dynamic'", "https:"]
    : [
        "'self'",
        "'unsafe-eval'",
        "'unsafe-inline'",
        "https://js.stripe.com",
        "https://checkout.stripe.com",
      ];

  const directives: Record<string, string[]> = {
    "default-src": ["'self'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'", "https://checkout.stripe.com"],
    "frame-ancestors": [allowsSelfFraming(pathname) ? "'self'" : "'none'"],
    "object-src": ["'none'"],
    "img-src": ["'self'", "data:", "blob:", "https:"],
    "font-src": ["'self'", "data:", "https://fonts.gstatic.com"],
    "style-src": [
      "'self'",
      "'unsafe-inline'",
      "https://fonts.googleapis.com",
    ],
    "script-src": scriptSrc,
    "connect-src": [
      "'self'",
      apiOrigin,
      "https://api.stripe.com",
      "https://checkout.stripe.com",
      ...supabaseConnectSrc,
      ...(isProd ? [] : ["ws:", "wss:"]),
    ],
    "frame-src": [
      "'self'",
      "https://js.stripe.com",
      "https://checkout.stripe.com",
    ],
    "worker-src": ["'self'", "blob:"],
    "manifest-src": ["'self'"],
  };

  if (isProd) directives["upgrade-insecure-requests"] = [];

  return Object.entries(directives)
    .map(([k, v]) => (v.length ? `${k} ${v.join(" ")}` : k))
    .join("; ");
}

function isMarketingPath(pathname: string): boolean {
  if (marketingRoutes.includes(pathname)) return true;
  // Allow generated SEO files served from app/ (sitemap.ts, robots.ts, opengraph-image.tsx).
  if (pathname === "/sitemap.xml" || pathname === "/robots.txt") return true;
  if (pathname.startsWith("/opengraph-image")) return true;
  return false;
}

function isPublicPrefix(pathname: string): boolean {
  return publicRoutePrefixes.some((p) => pathname.startsWith(p));
}

function decorate(
  response: NextResponse,
  requestId: string,
  csp: string,
): NextResponse {
  response.headers.set(REQUEST_ID_HEADER, requestId);
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

function resolveRequestId(headerValue: string | null): string {
  if (headerValue && isSafeRequestId(headerValue)) {
    return headerValue;
  }
  return newRequestId();
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const requestId = resolveRequestId(request.headers.get(REQUEST_ID_HEADER));

  const nonce = generateNonce();
  const csp = buildCsp(nonce, pathname);
  // Clone the incoming headers so we can attach the nonce + CSP and have
  // them flow into the renderer. Next.js auto-stamps `<script nonce>` when
  // it sees the `x-nonce` request header.
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", csp);

  // Skip auth refresh and routing for static internals.
  if (pathname.startsWith("/_next/")) {
    return decorate(
      NextResponse.next({ request: { headers: requestHeaders } }),
      requestId,
      csp,
    );
  }

  // Auth callback (/auth/callback, /auth/signout) and API routes manage
  // their own session/cookie writes — pass through with request_id only.
  if (pathname.startsWith("/auth/") || pathname.startsWith("/api/")) {
    const passThrough = NextResponse.next({
      request: { headers: requestHeaders },
    });
    return decorate(passThrough, requestId, csp);
  }

  // Refresh the Supabase session on every other request and read the user.
  // updateSession returns a response that carries any rotated auth cookies —
  // we MUST preserve those cookies on every redirect branch below.
  const { supabaseResponse, user } = await updateSession(
    request,
    requestHeaders,
  );
  const isAuthenticated = !!user;

  // Marketing routes — pass through with cookies + request_id.
  if (isMarketingPath(pathname)) {
    return decorate(supabaseResponse, requestId, csp);
  }

  // Redirect authenticated users away from auth pages, but NOT from
  // public-prefix paths like /invite/* (signed-in users may still need to accept).
  if (isAuthenticated && authRoutes.includes(pathname)) {
    const redirect = NextResponse.redirect(new URL("/dashboard", request.url));
    supabaseResponse.cookies.getAll().forEach((c) => {
      redirect.cookies.set(c.name, c.value);
    });
    return decorate(redirect, requestId, csp);
  }

  // Redirect unauthenticated users to login, except for public-prefix paths.
  if (
    !isAuthenticated &&
    !authRoutes.includes(pathname) &&
    !isPublicPrefix(pathname)
  ) {
    const url = new URL("/login", request.url);
    if (pathname && pathname !== "/") {
      url.searchParams.set("next", pathname);
    }
    const redirect = NextResponse.redirect(url);
    supabaseResponse.cookies.getAll().forEach((c) => {
      redirect.cookies.set(c.name, c.value);
    });
    return decorate(redirect, requestId, csp);
  }

  return decorate(supabaseResponse, requestId, csp);
}

export const config = {
  matcher: [
    /*
     * Match all paths except:
     * - _next/static (static files)
     * - _next/image (image optimization)
     * - favicon.ico
     */
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};
