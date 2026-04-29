"use server";

import { ApiError } from "@/lib/api-client";
import {
  listWebhookDeliveries,
  type WebhookDelivery,
} from "@/lib/webhooks";

export type FetchDeliveriesResult =
  | { ok: true; deliveries: WebhookDelivery[] }
  | { ok: false; error: string };

export async function fetchDeliveriesAction(
  webhookId: string,
): Promise<FetchDeliveriesResult> {
  if (!webhookId || typeof webhookId !== "string") {
    return { ok: false, error: "Missing webhook ID" };
  }
  try {
    const deliveries = await listWebhookDeliveries(webhookId);
    return { ok: true, deliveries };
  } catch (err) {
    if (err instanceof ApiError) return { ok: false, error: err.message };
    return { ok: false, error: "Failed to load deliveries" };
  }
}
