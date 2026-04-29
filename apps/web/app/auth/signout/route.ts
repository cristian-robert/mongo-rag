import { NextResponse, type NextRequest } from "next/server";

import { createClient } from "@/lib/supabase/server";

export const runtime = "nodejs";

/**
 * Sign-out endpoint. Supabase clears its cookies via the server client.
 * Accept POST only — never GET — so a malicious image or link can't log
 * the user out (CSRF surface).
 */
export async function POST(request: NextRequest) {
  const supabase = await createClient();
  await supabase.auth.signOut();
  return NextResponse.redirect(new URL("/login", request.url), {
    status: 303,
  });
}
