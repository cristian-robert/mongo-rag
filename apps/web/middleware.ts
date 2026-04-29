import { auth } from "@/lib/auth";
import {
  REQUEST_ID_HEADER,
  isSafeRequestId,
  newRequestId,
} from "@/lib/observability/logger";
import { NextResponse } from "next/server";

const publicRoutes = ["/login", "/signup", "/forgot-password", "/reset-password"];

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

  // Allow public routes and API routes — but still attach request_id.
  if (
    pathname.startsWith("/api/") ||
    pathname.startsWith("/_next/") ||
    pathname === "/"
  ) {
    return withRequestId(NextResponse.next(), requestId);
  }

  // Redirect authenticated users away from auth pages
  if (isAuthenticated && publicRoutes.includes(pathname)) {
    return withRequestId(
      NextResponse.redirect(new URL("/dashboard", req.url)),
      requestId,
    );
  }

  // Redirect unauthenticated users to login
  if (!isAuthenticated && !publicRoutes.includes(pathname)) {
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
