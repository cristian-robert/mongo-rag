/**
 * Server-side API client for the FastAPI backend.
 *
 * The FastAPI backend (issue #40) verifies Supabase RS256 access tokens via
 * the project's JWKS and joins the `profiles` row to derive `tenant_id`.
 * We forward the current request's Supabase access token as a Bearer.
 *
 * IMPORTANT: never call this from a client component — it touches the
 * server-only Supabase cookie store. Server actions / route handlers / RSC
 * only.
 */

import "server-only";

import { getAccessToken, getSession } from "@/lib/auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8100";

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
 * Reads the current Supabase session, forwards the access token as a
 * Bearer, returns the parsed JSON body. Throws ApiError on non-2xx
 * responses.
 */
export async function apiFetch<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const session = await getSession();
  if (!session?.user?.tenant_id) {
    throw new ApiError(401, "Not authenticated");
  }

  const token = await getAccessToken();
  if (!token) {
    throw new ApiError(401, "Not authenticated");
  }

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
