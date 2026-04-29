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

function withRequestId(
  response: NextResponse,
  requestId: string,
): NextResponse {
  response.headers.set(REQUEST_ID_HEADER, requestId);
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

  // Skip auth refresh and routing for static internals.
  if (pathname.startsWith("/_next/")) {
    return withRequestId(NextResponse.next({ request }), requestId);
  }

  // Auth callback (/auth/callback, /auth/signout) and API routes manage
  // their own session/cookie writes — pass through with request_id only.
  if (pathname.startsWith("/auth/") || pathname.startsWith("/api/")) {
    const passThrough = NextResponse.next({ request });
    return withRequestId(passThrough, requestId);
  }

  // Refresh the Supabase session on every other request and read the user.
  // updateSession returns a response that carries any rotated auth cookies —
  // we MUST preserve those cookies on every redirect branch below.
  const { supabaseResponse, user } = await updateSession(request);
  const isAuthenticated = !!user;

  // Marketing routes — pass through with cookies + request_id.
  if (isMarketingPath(pathname)) {
    return withRequestId(supabaseResponse, requestId);
  }

  // Redirect authenticated users away from auth pages, but NOT from
  // public-prefix paths like /invite/* (signed-in users may still need to accept).
  if (isAuthenticated && authRoutes.includes(pathname)) {
    const redirect = NextResponse.redirect(new URL("/dashboard", request.url));
    supabaseResponse.cookies.getAll().forEach((c) => {
      redirect.cookies.set(c.name, c.value);
    });
    return withRequestId(redirect, requestId);
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
    return withRequestId(redirect, requestId);
  }

  return withRequestId(supabaseResponse, requestId);
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
