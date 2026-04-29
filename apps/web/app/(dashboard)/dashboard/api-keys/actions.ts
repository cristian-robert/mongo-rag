"use server";

import { revalidatePath } from "next/cache";

import { ApiError } from "@/lib/api-client";
import {
  createApiKey as createApiKeyRequest,
  revokeApiKey as revokeApiKeyRequest,
  type CreatedApiKey,
} from "@/lib/api-keys";
import { createApiKeySchema } from "@/lib/validations/api-keys";

export type CreateKeyResult =
  | { ok: true; key: CreatedApiKey }
  | { ok: false; error: string };

export type RevokeKeyResult = { ok: true } | { ok: false; error: string };

const PAGE_PATH = "/dashboard/api-keys";

export async function createApiKeyAction(
  input: unknown,
): Promise<CreateKeyResult> {
  const parsed = createApiKeySchema.safeParse(input);
  if (!parsed.success) {
    return {
      ok: false,
      error: parsed.error.issues[0]?.message ?? "Invalid input",
    };
  }

  try {
    const key = await createApiKeyRequest(parsed.data);
    revalidatePath(PAGE_PATH);
    return { ok: true, key };
  } catch (err) {
    if (err instanceof ApiError) {
      return { ok: false, error: err.message };
    }
    return { ok: false, error: "Failed to create API key" };
  }
}

export async function revokeApiKeyAction(
  keyId: string,
): Promise<RevokeKeyResult> {
  if (!keyId || typeof keyId !== "string") {
    return { ok: false, error: "Missing key ID" };
  }
  try {
    await revokeApiKeyRequest(keyId);
    revalidatePath(PAGE_PATH);
    return { ok: true };
  } catch (err) {
    if (err instanceof ApiError) {
      return { ok: false, error: err.message };
    }
    return { ok: false, error: "Failed to revoke API key" };
  }
}
