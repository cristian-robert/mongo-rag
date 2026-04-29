import { NextResponse } from "next/server";

import { mintBackendToken } from "@/lib/api/token";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8100";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

async function proxy(
  id: string,
  init: RequestInit,
): Promise<NextResponse> {
  const minted = await mintBackendToken();
  if (!minted) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${minted.token}`);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let upstream: Response;
  try {
    upstream = await fetch(
      `${API_URL}/api/v1/documents/${encodeURIComponent(id)}`,
      { ...init, headers },
    );
  } catch (err) {
    console.error("[documents/proxy] upstream failed", {
      id,
      method: init.method,
      err: err instanceof Error ? err.message : String(err),
    });
    return NextResponse.json(
      { error: "Backend unavailable" },
      { status: 502 },
    );
  }

  if (upstream.status === 204) {
    return new NextResponse(null, { status: 204 });
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

export async function GET(
  _req: Request,
  ctx: { params: Promise<{ id: string }> },
) {
  const { id } = await ctx.params;
  return proxy(id, { method: "GET" });
}

export async function PATCH(
  req: Request,
  ctx: { params: Promise<{ id: string }> },
) {
  const { id } = await ctx.params;
  const body = await req.text();
  return proxy(id, { method: "PATCH", body });
}

export async function DELETE(
  _req: Request,
  ctx: { params: Promise<{ id: string }> },
) {
  const { id } = await ctx.params;
  return proxy(id, { method: "DELETE" });
}
