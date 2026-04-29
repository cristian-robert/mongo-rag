import { NextResponse, type NextRequest } from "next/server";

import { createClient } from "@/lib/supabase/server";

export const runtime = "nodejs";

/**
 * Email-confirmation and OAuth-redirect callback.
 *
 * Supabase appends `?code=...` after a successful magic-link / email
 * confirmation. We exchange it for a session (which sets cookies via the
 * server client) and redirect to `next` if it's a same-origin path,
 * otherwise to `/dashboard`.
 *
 * Security: only allow same-origin `next` paths to prevent open redirects.
 */
export async function GET(request: NextRequest) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const nextParam = url.searchParams.get("next") ?? "/dashboard";

  // Only allow same-origin redirect targets that start with "/" and not "//".
  const safeNext =
    nextParam.startsWith("/") && !nextParam.startsWith("//")
      ? nextParam
      : "/dashboard";

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      return NextResponse.redirect(new URL(safeNext, request.url));
    }
  }

  return NextResponse.redirect(
    new URL("/login?error=callback_failed", request.url),
  );
}
