/**
 * Server-side API client for the FastAPI backend.
 *
 * The FastAPI backend authenticates dashboard requests with HS256 JWTs signed
 * using `NEXTAUTH_SECRET` and a `tenant_id` claim (see apps/api/src/core/tenant.py).
 *
 * NextAuth's session cookie is encrypted (JWE) and cannot be forwarded directly,
 * so we mint a short-lived signed token from the server-side session.
 *
 * IMPORTANT: never call this from a client component. Server actions / route
 * handlers / RSC only — the secret must never reach the browser.
 */

import "server-only";

import { SignJWT } from "jose";

import { auth } from "@/lib/auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8100";
const TOKEN_TTL_SECONDS = 60;

function getSecret(): Uint8Array {
  const secret = process.env.NEXTAUTH_SECRET;
  if (!secret) {
    throw new Error("NEXTAUTH_SECRET is not configured");
  }
  return new TextEncoder().encode(secret);
}

async function mintBackendToken(params: {
  sub: string;
  tenantId: string;
  role: string;
}): Promise<string> {
  return new SignJWT({ tenant_id: params.tenantId, role: params.role })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(params.sub)
    .setIssuedAt()
    .setExpirationTime(`${TOKEN_TTL_SECONDS}s`)
    .sign(getSecret());
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
  body?: unknown;
};

/**
 * Authenticated fetch against the FastAPI backend.
 *
 * Reads the current NextAuth session, mints a short-lived HS256 JWT, and
 * sends it as a Bearer token. Returns the parsed JSON body. Throws ApiError
 * on non-2xx responses.
 */
export async function apiFetch<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const session = await auth();
  if (!session?.user?.tenant_id) {
    throw new ApiError(401, "Not authenticated");
  }

  const token = await mintBackendToken({
    sub: session.user.id,
    tenantId: session.user.tenant_id,
    role: session.user.role,
  });

  const url = `${API_URL}${path}`;
  const response = await fetch(url, {
    method: options.method ?? "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
    cache: "no-store",
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const data = (await response.json()) as { detail?: string };
      if (data?.detail) message = data.detail;
    } catch {
      // ignore parse errors
    }
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
