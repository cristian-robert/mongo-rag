import { NextResponse } from "next/server";

// Liveness probe consumed by the Dockerfile HEALTHCHECK and platform
// load balancers. Intentionally cheap — does NOT touch the DB or the
// upstream API. Use a separate /api/ready endpoint if dependency
// readiness needs to be checked.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export function GET(): NextResponse {
  return NextResponse.json({ status: "ok" }, { status: 200 });
}
