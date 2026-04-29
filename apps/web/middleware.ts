import { auth } from "@/lib/auth";
import {
  REQUEST_ID_HEADER,
  isSafeRequestId,
  newRequestId,
} from "@/lib/observability/request-id";
import { NextResponse } from "next/server";

const authRoutes = ["/login", "/signup", "/forgot-password", "/reset-password"];

// Marketing routes are public and never trigger auth redirects.
const marketingRoutes = ["/", "/pricing"];

// Public path prefixes — accessible without auth, no auto-redirect either way.
const publicRoutePrefixes = ["/invite/"];

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

function withRequestId(response: NextResponse, requestId: string): NextResponse {
  response.headers.set(REQUEST_ID_HEADER, requestId);
  return response;
}

function resolveRequestId(headerValue: string | null): string {
  if (headerValue && isSafeRequestId(headerValue)) {
    return headerValue;
  }
  return newRequestId();
}

export default auth((req) => {
  const { pathname } = req.nextUrl;
  const isAuthenticated = !!req.auth;
  const requestId = resolveRequestId(req.headers.get(REQUEST_ID_HEADER));

  // Allow API routes, internals, and marketing/SEO routes — but still attach request_id.
  if (
    pathname.startsWith("/api/") ||
    pathname.startsWith("/_next/") ||
    isMarketingPath(pathname)
  ) {
    return withRequestId(NextResponse.next(), requestId);
  }

  // Redirect authenticated users away from auth pages, but NOT from
  // public-prefix paths like /invite/* (signed-in users may still need to accept).
  if (isAuthenticated && authRoutes.includes(pathname)) {
    return withRequestId(
      NextResponse.redirect(new URL("/dashboard", req.url)),
      requestId,
    );
  }

  // Redirect unauthenticated users to login, except for public paths.
  if (
    !isAuthenticated &&
    !authRoutes.includes(pathname) &&
    !isPublicPrefix(pathname)
  ) {
    return withRequestId(
      NextResponse.redirect(new URL("/login", req.url)),
      requestId,
    );
  }

  return withRequestId(NextResponse.next(), requestId);
});

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
