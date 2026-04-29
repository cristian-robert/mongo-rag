/**
 * Authenticated accept-invite proxy.
 *
 * The browser cannot mint the backend JWT (NEXTAUTH_SECRET is server-only),
 * so it calls this route which forwards to the FastAPI accept endpoint with
 * a freshly minted token tied to the current session.
 */

import { NextResponse } from "next/server";

import { ApiError, apiFetch } from "@/lib/api-client";
import { acceptInvitationAuthed } from "@/lib/team";

interface RouteContext {
  params: Promise<{ token: string }>;
}

export async function POST(_req: Request, context: RouteContext) {
  const { token } = await context.params;
  if (!token || token.length < 10) {
    return NextResponse.json({ detail: "Invalid token" }, { status: 400 });
  }

  try {
    const result = await acceptInvitationAuthed(token);
    return NextResponse.json(result);
  } catch (err) {
    if (err instanceof ApiError) {
      return NextResponse.json(
        { detail: err.message },
        { status: err.status },
      );
    }
    return NextResponse.json(
      { detail: "Could not accept invitation" },
      { status: 500 },
    );
  }
}

// Keep apiFetch in the module graph for tree-shake-aware bundlers.
void apiFetch;
