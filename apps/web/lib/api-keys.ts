/**
 * Typed client functions for the FastAPI /api/v1/keys endpoints.
 *
 * Server-only — these helpers mint a backend JWT, so they must never run in
 * the browser. Use them from Server Components or Server Actions.
 */

import "server-only";

import { apiFetch } from "@/lib/api-client";

export type ApiKeyPermission = "chat" | "search";

export interface ApiKey {
  id: string;
  key_prefix: string;
  name: string;
  permissions: ApiKeyPermission[];
  is_revoked: boolean;
  last_used_at: string | null;
  created_at: string;
}

export interface ApiKeyListResponse {
  keys: ApiKey[];
}

export interface CreatedApiKey {
  raw_key: string;
  key_prefix: string;
  name: string;
  permissions: ApiKeyPermission[];
  created_at: string;
}

export interface CreateApiKeyInput {
  name: string;
  permissions?: ApiKeyPermission[];
}

export async function listApiKeys(): Promise<ApiKey[]> {
  const data = await apiFetch<ApiKeyListResponse>("/api/v1/keys");
  return data.keys;
}

export async function createApiKey(
  input: CreateApiKeyInput,
): Promise<CreatedApiKey> {
  return apiFetch<CreatedApiKey>("/api/v1/keys", {
    method: "POST",
    body: {
      name: input.name,
      permissions: input.permissions ?? ["chat", "search"],
    },
  });
}

export async function revokeApiKey(keyId: string): Promise<void> {
  await apiFetch<{ message: string }>(`/api/v1/keys/${keyId}`, {
    method: "DELETE",
  });
}
