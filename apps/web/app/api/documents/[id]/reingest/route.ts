import { NextResponse } from "next/server";

import { mintBackendToken } from "@/lib/api/token";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8100";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(
  _req: Request,
  ctx: { params: Promise<{ id: string }> },
) {
  const { id } = await ctx.params;
  const minted = await mintBackendToken();
  if (!minted) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  let upstream: Response;
  try {
    upstream = await fetch(
      `${API_URL}/api/v1/documents/${encodeURIComponent(id)}/reingest`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${minted.token}` },
      },
    );
  } catch (err) {
    console.error("[documents/reingest] upstream failed", {
      id,
      err: err instanceof Error ? err.message : String(err),
    });
    return NextResponse.json(
      { error: "Backend unavailable" },
      { status: 502 },
    );
  }

  const text = await upstream.text();
  return new NextResponse(text, {
    status: upstream.status,
    headers: {
      "Content-Type":
        upstream.headers.get("Content-Type") ?? "application/json",
    },
  });
}
