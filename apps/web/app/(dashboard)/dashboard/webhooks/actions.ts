"use server";

import { revalidatePath } from "next/cache";

import { ApiError } from "@/lib/api-client";
import {
  createWebhook as createWebhookRequest,
  deleteWebhook as deleteWebhookRequest,
  testFireWebhook as testFireWebhookRequest,
  updateWebhook as updateWebhookRequest,
  type CreatedWebhook,
  type WebhookEvent,
} from "@/lib/webhooks";
import { createWebhookSchema, webhookEvents } from "@/lib/validations/webhooks";
import { z } from "zod/v3";

export type CreateWebhookResult =
  | { ok: true; webhook: CreatedWebhook }
  | { ok: false; error: string };

export type SimpleResult = { ok: true } | { ok: false; error: string };

const PAGE_PATH = "/dashboard/webhooks";

export async function createWebhookAction(
  input: unknown,
): Promise<CreateWebhookResult> {
  const parsed = createWebhookSchema.safeParse(input);
  if (!parsed.success) {
    return {
      ok: false,
      error: parsed.error.issues[0]?.message ?? "Invalid input",
    };
  }
  try {
    const webhook = await createWebhookRequest({
      url: parsed.data.url,
      events: parsed.data.events,
      description: parsed.data.description || undefined,
      active: parsed.data.active,
    });
    revalidatePath(PAGE_PATH);
    return { ok: true, webhook };
  } catch (err) {
    if (err instanceof ApiError) return { ok: false, error: err.message };
    return { ok: false, error: "Failed to create webhook" };
  }
}

export async function deleteWebhookAction(
  webhookId: string,
): Promise<SimpleResult> {
  if (!webhookId || typeof webhookId !== "string") {
    return { ok: false, error: "Missing webhook ID" };
  }
  try {
    await deleteWebhookRequest(webhookId);
    revalidatePath(PAGE_PATH);
    return { ok: true };
  } catch (err) {
    if (err instanceof ApiError) return { ok: false, error: err.message };
    return { ok: false, error: "Failed to delete webhook" };
  }
}

export async function toggleWebhookAction(
  webhookId: string,
  active: boolean,
): Promise<SimpleResult> {
  if (!webhookId || typeof webhookId !== "string") {
    return { ok: false, error: "Missing webhook ID" };
  }
  try {
    await updateWebhookRequest(webhookId, { active });
    revalidatePath(PAGE_PATH);
    return { ok: true };
  } catch (err) {
    if (err instanceof ApiError) return { ok: false, error: err.message };
    return { ok: false, error: "Failed to update webhook" };
  }
}

const testFireSchema = z.object({
  webhookId: z.string().min(1),
  event: z.enum(webhookEvents),
});

export async function testFireWebhookAction(
  input: unknown,
): Promise<SimpleResult> {
  const parsed = testFireSchema.safeParse(input);
  if (!parsed.success) {
    return { ok: false, error: "Invalid request" };
  }
  try {
    await testFireWebhookRequest(
      parsed.data.webhookId,
      parsed.data.event as WebhookEvent,
    );
    revalidatePath(PAGE_PATH);
    return { ok: true };
  } catch (err) {
    if (err instanceof ApiError) return { ok: false, error: err.message };
    return { ok: false, error: "Failed to fire test event" };
  }
}
