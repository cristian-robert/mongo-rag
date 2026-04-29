import { describe, expect, it, beforeEach } from "vitest";

beforeEach(() => {
  process.env.NEXT_PUBLIC_SUPABASE_URL = "https://example.supabase.co";
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = "sb_publishable_test";
});

describe("supabase browser client", () => {
  it("creates a browser client with publishable key", async () => {
    const { createClient } = await import("./client");
    const client = createClient();
    expect(client).toBeDefined();
    expect(typeof client.auth.signInWithPassword).toBe("function");
    expect(typeof client.auth.signUp).toBe("function");
    expect(typeof client.auth.resetPasswordForEmail).toBe("function");
    expect(typeof client.auth.signOut).toBe("function");
  });
});
