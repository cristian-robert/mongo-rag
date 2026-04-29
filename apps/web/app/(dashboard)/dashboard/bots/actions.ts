"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { ApiError } from "@/lib/api-client";
import {
  createBot as createBotRequest,
  deleteBot as deleteBotRequest,
  updateBot as updateBotRequest,
  type Bot,
} from "@/lib/bots";
import { createBotSchema, updateBotSchema } from "@/lib/validations/bots";

export type CreateBotResult =
  | { ok: true; bot: Bot }
  | { ok: false; error: string };

export type UpdateBotResult =
  | { ok: true; bot: Bot }
  | { ok: false; error: string };

export type DeleteBotResult = { ok: true } | { ok: false; error: string };

const BOTS_PATH = "/dashboard/bots";

function botPath(id: string): string {
  return `${BOTS_PATH}/${id}`;
}

export async function createBotAction(input: unknown): Promise<CreateBotResult> {
  const parsed = createBotSchema.safeParse(input);
  if (!parsed.success) {
    return {
      ok: false,
      error: parsed.error.issues[0]?.message ?? "Invalid input",
    };
  }

  try {
    // Strip empty description so the API treats it as null.
    const payload = { ...parsed.data };
    if (payload.description === "") delete payload.description;
    if (payload.widget_config.avatar_url === "")
      payload.widget_config.avatar_url = undefined;

    const bot = await createBotRequest({
      ...payload,
      description: payload.description,
      widget_config: {
        ...payload.widget_config,
        avatar_url: payload.widget_config.avatar_url ?? null,
      },
    });
    revalidatePath(BOTS_PATH);
    return { ok: true, bot };
  } catch (err) {
    if (err instanceof ApiError) {
      return { ok: false, error: err.message };
    }
    return { ok: false, error: "Failed to create bot" };
  }
}

export async function updateBotAction(
  id: string,
  input: unknown,
): Promise<UpdateBotResult> {
  if (!id || typeof id !== "string") {
    return { ok: false, error: "Missing bot id" };
  }
  const parsed = updateBotSchema.safeParse(input);
  if (!parsed.success) {
    return {
      ok: false,
      error: parsed.error.issues[0]?.message ?? "Invalid input",
    };
  }
  try {
    const payload = { ...parsed.data };
    if (payload.description === "") payload.description = undefined;
    if (
      payload.widget_config &&
      payload.widget_config.avatar_url === ""
    ) {
      payload.widget_config.avatar_url = undefined;
    }
    const bot = await updateBotRequest(id, {
      ...payload,
      widget_config: payload.widget_config
        ? {
            ...payload.widget_config,
            avatar_url: payload.widget_config.avatar_url ?? null,
          }
        : undefined,
    });
    revalidatePath(BOTS_PATH);
    revalidatePath(botPath(id));
    return { ok: true, bot };
  } catch (err) {
    if (err instanceof ApiError) {
      return { ok: false, error: err.message };
    }
    return { ok: false, error: "Failed to update bot" };
  }
}

export async function deleteBotAction(id: string): Promise<DeleteBotResult> {
  if (!id || typeof id !== "string") {
    return { ok: false, error: "Missing bot id" };
  }
  try {
    await deleteBotRequest(id);
    revalidatePath(BOTS_PATH);
    return { ok: true };
  } catch (err) {
    if (err instanceof ApiError) {
      return { ok: false, error: err.message };
    }
    return { ok: false, error: "Failed to delete bot" };
  }
}

export async function deleteBotAndRedirectAction(id: string): Promise<void> {
  const result = await deleteBotAction(id);
  if (!result.ok) {
    // Surface the error via search param so the page can display it.
    redirect(`${BOTS_PATH}?error=${encodeURIComponent(result.error)}`);
  }
  redirect(BOTS_PATH);
}
