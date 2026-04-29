/**
 * Unit tests for the server-side API client.
 *
 * The client mints a short-lived HS256 JWT from the NextAuth session and
 * forwards it as a Bearer token. These tests exercise the auth → token →
 * fetch glue without spinning up a real backend.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { jwtVerify } from "jose";

// next-auth must be mocked before importing api-client because the module
// imports `auth` eagerly via `@/lib/auth`.
const authMock = vi.fn();
vi.mock("@/lib/auth", () => ({ auth: authMock }));
// `server-only` throws in test env unless mocked away.
vi.mock("server-only", () => ({}));

const SECRET = "test-secret-for-unit-tests-minimum-32chars";

beforeEach(() => {
  process.env.NEXTAUTH_SECRET = SECRET;
  process.env.NEXT_PUBLIC_API_URL = "http://api.test";
  authMock.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiFetch", () => {
  it("throws ApiError(401) when no session is available", async () => {
    authMock.mockResolvedValueOnce(null);
    const { apiFetch, ApiError } = await import("./api-client");

    await expect(apiFetch("/anything")).rejects.toBeInstanceOf(ApiError);
    await expect(apiFetch("/anything")).rejects.toMatchObject({ status: 401 });
  });

  it("mints a HS256 JWT with tenant_id and forwards as Bearer", async () => {
    authMock.mockResolvedValue({
      user: { id: "user-1", tenant_id: "tenant-A", role: "owner" },
    });
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
    const auth = init.headers.Authorization as string;
    expect(auth.startsWith("Bearer ")).toBe(true);

    const token = auth.slice("Bearer ".length);
    const { payload, protectedHeader } = await jwtVerify(
      token,
      new TextEncoder().encode(SECRET),
    );
    expect(protectedHeader.alg).toBe("HS256");
    expect(payload.sub).toBe("user-1");
    expect(payload.tenant_id).toBe("tenant-A");
    expect(payload.role).toBe("owner");
  });

  it("returns undefined for 204 No Content responses", async () => {
    authMock.mockResolvedValue({
      user: { id: "u", tenant_id: "t", role: "owner" },
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));

    const { apiFetch } = await import("./api-client");
    const result = await apiFetch<undefined>("/api/v1/keys/x", { method: "DELETE" });
    expect(result).toBeUndefined();
  });

  it("surfaces backend `detail` strings on errors", async () => {
    authMock.mockResolvedValue({
      user: { id: "u", tenant_id: "t", role: "owner" },
    });
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
    const err = await apiFetch("/api/v1/chat").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(429);
    expect(err.message).toBe("quota exceeded");
  });

  it("falls back to a generic message when the error body is unparseable", async () => {
    authMock.mockResolvedValue({
      user: { id: "u", tenant_id: "t", role: "owner" },
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("<html>500</html>", { status: 500 })),
    );

    const { apiFetch } = await import("./api-client");
    const err = await apiFetch("/api/v1/anything").catch((e) => e);
    expect(err.status).toBe(500);
    expect(err.message).toMatch(/Request failed \(500\)/);
  });
});
