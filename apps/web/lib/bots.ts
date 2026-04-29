/**
 * Server-only client for the FastAPI /api/v1/bots endpoints.
 *
 * Mints the backend JWT via apiFetch, so it must never run in the browser.
 */

import "server-only";

import { apiFetch } from "@/lib/api-client";

export type BotTone =
  | "professional"
  | "friendly"
  | "concise"
  | "technical"
  | "playful";

export type WidgetPosition = "bottom-right" | "bottom-left";

export interface ModelConfig {
  temperature: number;
  max_tokens: number;
}

export interface WidgetConfig {
  primary_color: string;
  position: WidgetPosition;
  avatar_url: string | null;
}

export interface DocumentFilter {
  mode: "all" | "ids";
  document_ids: string[];
}

export interface Bot {
  id: string;
  tenant_id: string;
  name: string;
  slug: string;
  description: string | null;
  system_prompt: string;
  welcome_message: string;
  tone: BotTone;
  is_public: boolean;
  model_config: ModelConfig;
  widget_config: WidgetConfig;
  document_filter: DocumentFilter;
  created_at: string;
  updated_at: string;
}

export interface BotListResponse {
  bots: Bot[];
}

export interface CreateBotInput {
  name: string;
  slug: string;
  description?: string;
  system_prompt: string;
  welcome_message: string;
  tone: BotTone;
  is_public: boolean;
  model_config: ModelConfig;
  widget_config: WidgetConfig;
  document_filter: DocumentFilter;
}

export type UpdateBotInput = Partial<Omit<CreateBotInput, "slug">>;

export async function listBots(): Promise<Bot[]> {
  const data = await apiFetch<BotListResponse>("/api/v1/bots");
  return data.bots;
}

export async function getBot(id: string): Promise<Bot> {
  return apiFetch<Bot>(`/api/v1/bots/${id}`);
}

export async function createBot(input: CreateBotInput): Promise<Bot> {
  return apiFetch<Bot>("/api/v1/bots", {
    method: "POST",
    body: input,
  });
}

export async function updateBot(
  id: string,
  input: UpdateBotInput,
): Promise<Bot> {
  return apiFetch<Bot>(`/api/v1/bots/${id}`, {
    method: "PUT",
    body: input,
  });
}

export async function deleteBot(id: string): Promise<void> {
  await apiFetch<{ message: string }>(`/api/v1/bots/${id}`, {
    method: "DELETE",
  });
}
