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

export type ColorMode = "light" | "dark" | "auto";
export type RadiusToken = "none" | "sm" | "md" | "lg" | "full";
export type DensityToken = "compact" | "comfortable" | "spacious";
export type SizeToken = "sm" | "md" | "lg";
export type LauncherShape = "circle" | "rounded-square" | "pill";
export type LauncherIcon = "chat" | "sparkle" | "book" | "question" | "custom";

/** All fields optional on the wire — Zod-parsed input may pass undefined,
 *  server responses return null. Either is acceptable. */
export interface WidgetDarkOverrides {
  background?: string | null;
  surface?: string | null;
  foreground?: string | null;
  muted?: string | null;
  border?: string | null;
  primary?: string | null;
  primary_foreground?: string | null;
}

/**
 * Cosmetic widget config. Fields optional with `?: T | null | undefined`
 * because:
 *   - Server responses fill in defaults, so values come back as the
 *     concrete type or null where unset.
 *   - Zod parses form input to T | undefined for optional fields.
 *   - Pydantic on the server accepts both null and missing for Optional[T].
 *
 * The dashboard form widens the type and the API request happily JSON-
 * stringifies undefined fields away.
 */
export interface WidgetConfig {
  // Existing
  primary_color: string;
  position: WidgetPosition;
  avatar_url?: string | null;
  // Color tokens (#87)
  color_mode?: ColorMode;
  background?: string | null;
  surface?: string | null;
  foreground?: string | null;
  muted?: string | null;
  border?: string | null;
  primary_foreground?: string | null;
  dark_overrides?: WidgetDarkOverrides | null;
  // Typography
  font_family?: string;
  display_font?: string | null;
  base_font_size?: SizeToken;
  // Shape & density
  radius?: RadiusToken;
  density?: DensityToken;
  launcher_shape?: LauncherShape;
  launcher_size?: SizeToken;
  panel_size?: SizeToken;
  // Branding & icons
  launcher_icon?: LauncherIcon;
  launcher_icon_url?: string | null;
  show_avatar_in_messages?: boolean;
  branding_text?: string | null;
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
