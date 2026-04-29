/**
 * Unit tests for the server-side API client.
 *
 * The client reads the current Supabase session and forwards the access
 * token as a Bearer to the FastAPI backend.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ApiError as ApiErrorType } from "./api-client";

const getSessionMock = vi.fn();
const getAccessTokenMock = vi.fn();
vi.mock("@/lib/auth", () => ({
  getSession: getSessionMock,
  getAccessToken: getAccessTokenMock,
}));
// `server-only` throws in test env unless mocked away.
vi.mock("server-only", () => ({}));

beforeEach(() => {
  process.env.NEXT_PUBLIC_API_URL = "http://api.test";
  getSessionMock.mockReset();
  getAccessTokenMock.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiFetch", () => {
  it("throws ApiError(401) when no session is available", async () => {
    getSessionMock.mockResolvedValueOnce(null);
    const { apiFetch, ApiError } = await import("./api-client");

    await expect(apiFetch("/anything")).rejects.toBeInstanceOf(ApiError);
    await expect(apiFetch("/anything")).rejects.toMatchObject({ status: 401 });
  });

  it("throws ApiError(401) when session has no access token", async () => {
    getSessionMock.mockResolvedValue({
      user: { id: "u", tenant_id: "t", role: "owner", email: "x@y.z", name: null },
    });
    getAccessTokenMock.mockResolvedValueOnce(null);
    const { apiFetch, ApiError } = await import("./api-client");
    await expect(apiFetch("/x")).rejects.toBeInstanceOf(ApiError);
    await expect(apiFetch("/x")).rejects.toMatchObject({ status: 401 });
  });

  it("forwards the Supabase access token as Bearer", async () => {
    getSessionMock.mockResolvedValue({
      user: { id: "u", tenant_id: "t", role: "owner", email: "x@y.z", name: null },
    });
    getAccessTokenMock.mockResolvedValue("supabase.access.token");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { apiFetch } = await import("./api-client");
    const result = await apiFetch<{ ok: boolean }>("/api/v1/usage");

    expect(result).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api.test/api/v1/usage");
    expect(init.method).toBe("GET");
    expect(init.headers.Authorization).toBe("Bearer supabase.access.token");
  });

  it("returns undefined for 204 No Content responses", async () => {
    getSessionMock.mockResolvedValue({
      user: { id: "u", tenant_id: "t", role: "owner", email: "x@y.z", name: null },
    });
    getAccessTokenMock.mockResolvedValue("tok");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(null, { status: 204 })),
    );

    const { apiFetch } = await import("./api-client");
    const result = await apiFetch<undefined>("/api/v1/keys/x", {
      method: "DELETE",
    });
    expect(result).toBeUndefined();
  });

  it("surfaces backend `detail` strings on errors", async () => {
    getSessionMock.mockResolvedValue({
      user: { id: "u", tenant_id: "t", role: "owner", email: "x@y.z", name: null },
    });
    getAccessTokenMock.mockResolvedValue("tok");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "quota exceeded" }), {
          status: 429,
          headers: { "content-type": "application/json" },
        }),
      ),
    );

    const { apiFetch, ApiError } = await import("./api-client");
    const err = await apiFetch("/api/v1/chat").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiErrorType).status).toBe(429);
    expect((err as ApiErrorType).message).toBe("quota exceeded");
  });

  it("falls back to a generic message when the error body is unparseable", async () => {
    getSessionMock.mockResolvedValue({
      user: { id: "u", tenant_id: "t", role: "owner", email: "x@y.z", name: null },
    });
    getAccessTokenMock.mockResolvedValue("tok");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("<html>500</html>", { status: 500 }),
      ),
    );

    const { apiFetch, ApiError } = await import("./api-client");
    const err = await apiFetch("/api/v1/anything").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiErrorType).status).toBe(500);
    expect((err as ApiErrorType).message).toMatch(/Request failed \(500\)/);
  });
});
