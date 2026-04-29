/**
 * Typed client functions for the FastAPI /api/v1/webhooks endpoints.
 *
 * Server-only — these helpers mint a backend JWT, so they must never run in
 * the browser. Use them from Server Components or Server Actions.
 */

import "server-only";

import { apiFetch } from "@/lib/api-client";

export const WEBHOOK_EVENTS = [
  "document.ingested",
  "document.deleted",
  "chat.completed",
  "subscription.updated",
] as const;

export type WebhookEvent = (typeof WEBHOOK_EVENTS)[number];

export interface Webhook {
  id: string;
  url: string;
  events: WebhookEvent[];
  description: string | null;
  active: boolean;
  secret_prefix: string;
  created_at: string;
  updated_at: string;
}

export interface CreatedWebhook extends Webhook {
  secret: string;
}

export interface WebhookDelivery {
  id: string;
  webhook_id: string;
  event: string;
  status: "pending" | "delivered" | "failed";
  attempts: number;
  response_code: number | null;
  last_error: string | null;
  created_at: string;
  delivered_at: string | null;
}

export interface CreateWebhookInput {
  url: string;
  events: WebhookEvent[];
  description?: string;
  active?: boolean;
}

export interface UpdateWebhookInput {
  url?: string;
  events?: WebhookEvent[];
  description?: string | null;
  active?: boolean;
}

export async function listWebhooks(): Promise<Webhook[]> {
  const data = await apiFetch<{ webhooks: Webhook[] }>("/api/v1/webhooks");
  return data.webhooks;
}

export async function createWebhook(
  input: CreateWebhookInput,
): Promise<CreatedWebhook> {
  return apiFetch<CreatedWebhook>("/api/v1/webhooks", {
    method: "POST",
    body: input,
  });
}

export async function updateWebhook(
  webhookId: string,
  input: UpdateWebhookInput,
): Promise<Webhook> {
  return apiFetch<Webhook>(`/api/v1/webhooks/${webhookId}`, {
    method: "PATCH",
    body: input,
  });
}

export async function deleteWebhook(webhookId: string): Promise<void> {
  await apiFetch<{ message: string }>(`/api/v1/webhooks/${webhookId}`, {
    method: "DELETE",
  });
}

export async function testFireWebhook(
  webhookId: string,
  event: WebhookEvent,
): Promise<void> {
  await apiFetch<{ message: string }>(
    `/api/v1/webhooks/${webhookId}/test`,
    { method: "POST", body: { event } },
  );
}

export async function listWebhookDeliveries(
  webhookId: string,
): Promise<WebhookDelivery[]> {
  const data = await apiFetch<{ deliveries: WebhookDelivery[] }>(
    `/api/v1/webhooks/${webhookId}/deliveries?limit=25`,
  );
  return data.deliveries;
}
