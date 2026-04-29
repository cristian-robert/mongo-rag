/**
 * Typed client for the FastAPI /api/v1/team endpoints.
 *
 * Server-only — these helpers mint a backend JWT.
 */

import "server-only";

import { apiFetch } from "@/lib/api-client";

export type TeamRole = "owner" | "admin" | "member" | "viewer";

export const ROLE_RANK: Record<TeamRole, number> = {
  viewer: 0,
  member: 1,
  admin: 2,
  owner: 3,
};

export function hasMinRole(role: TeamRole | string, min: TeamRole): boolean {
  const a = ROLE_RANK[role as TeamRole];
  const b = ROLE_RANK[min];
  if (a === undefined) return false;
  return a >= b;
}

export interface Member {
  id: string;
  email: string;
  name: string;
  role: TeamRole;
  is_active: boolean;
  created_at: string;
}

export interface Invitation {
  id: string;
  email: string;
  role: TeamRole;
  expires_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

export interface CreatedInvitation {
  invitation: Invitation;
  accept_url: string;
}

export interface Me {
  user_id: string;
  tenant_id: string;
  email: string;
  name: string;
  role: TeamRole;
}

export async function getMe(): Promise<Me> {
  return apiFetch<Me>("/api/v1/auth/me");
}

export async function listMembers(): Promise<Member[]> {
  const r = await apiFetch<{ members: Member[] }>("/api/v1/team/members");
  return r.members;
}

export async function listInvitations(): Promise<Invitation[]> {
  const r = await apiFetch<{ invitations: Invitation[] }>(
    "/api/v1/team/invitations",
  );
  return r.invitations;
}

export async function createInvitation(input: {
  email: string;
  role: TeamRole;
}): Promise<CreatedInvitation> {
  return apiFetch<CreatedInvitation>("/api/v1/team/invitations", {
    method: "POST",
    body: input,
  });
}

export async function revokeInvitation(invitationId: string): Promise<void> {
  await apiFetch<{ message: string }>(
    `/api/v1/team/invitations/${invitationId}`,
    { method: "DELETE" },
  );
}

export async function updateMemberRole(input: {
  userId: string;
  role: TeamRole;
}): Promise<Member> {
  return apiFetch<Member>(`/api/v1/team/members/${input.userId}`, {
    method: "PATCH",
    body: { role: input.role },
  });
}

export async function removeMember(userId: string): Promise<void> {
  await apiFetch<{ message: string }>(`/api/v1/team/members/${userId}`, {
    method: "DELETE",
  });
}

export async function acceptInvitationAuthed(token: string): Promise<{
  user_id: string;
  tenant_id: string;
  role: TeamRole;
  email: string;
  name: string;
}> {
  return apiFetch(`/api/v1/team/invitations/${token}/accept`, {
    method: "POST",
    body: { token },
  });
}
