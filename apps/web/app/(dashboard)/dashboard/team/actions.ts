"use server";

import { revalidatePath } from "next/cache";

import { ApiError } from "@/lib/api-client";
import {
  createInvitation,
  removeMember,
  revokeInvitation,
  updateMemberRole,
  type CreatedInvitation,
  type TeamRole,
} from "@/lib/team";
import {
  inviteMemberSchema,
  updateMemberRoleSchema,
} from "@/lib/validations/team";

export type CreateInviteResult =
  | { ok: true; data: CreatedInvitation }
  | { ok: false; error: string };

export type SimpleResult = { ok: true } | { ok: false; error: string };

const PAGE_PATH = "/dashboard/team";

export async function inviteMemberAction(
  input: unknown,
): Promise<CreateInviteResult> {
  const parsed = inviteMemberSchema.safeParse(input);
  if (!parsed.success) {
    return {
      ok: false,
      error: parsed.error.issues[0]?.message ?? "Invalid input",
    };
  }
  try {
    const data = await createInvitation(parsed.data);
    revalidatePath(PAGE_PATH);
    return { ok: true, data };
  } catch (err) {
    if (err instanceof ApiError) return { ok: false, error: err.message };
    return { ok: false, error: "Failed to create invitation" };
  }
}

export async function revokeInvitationAction(
  invitationId: string,
): Promise<SimpleResult> {
  if (!invitationId) return { ok: false, error: "Missing invitation id" };
  try {
    await revokeInvitation(invitationId);
    revalidatePath(PAGE_PATH);
    return { ok: true };
  } catch (err) {
    if (err instanceof ApiError) return { ok: false, error: err.message };
    return { ok: false, error: "Failed to revoke invitation" };
  }
}

export async function updateMemberRoleAction(
  input: unknown,
): Promise<SimpleResult> {
  const parsed = updateMemberRoleSchema.safeParse(input);
  if (!parsed.success) {
    return {
      ok: false,
      error: parsed.error.issues[0]?.message ?? "Invalid input",
    };
  }
  try {
    await updateMemberRole({
      userId: parsed.data.user_id,
      role: parsed.data.role as TeamRole,
    });
    revalidatePath(PAGE_PATH);
    return { ok: true };
  } catch (err) {
    if (err instanceof ApiError) return { ok: false, error: err.message };
    return { ok: false, error: "Failed to update role" };
  }
}

export async function removeMemberAction(
  userId: string,
): Promise<SimpleResult> {
  if (!userId) return { ok: false, error: "Missing user id" };
  try {
    await removeMember(userId);
    revalidatePath(PAGE_PATH);
    return { ok: true };
  } catch (err) {
    if (err instanceof ApiError) return { ok: false, error: err.message };
    return { ok: false, error: "Failed to remove member" };
  }
}
