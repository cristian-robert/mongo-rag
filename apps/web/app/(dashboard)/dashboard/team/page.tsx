import type { Metadata } from "next";

import { ApiError } from "@/lib/api-client";
import {
  getMe,
  hasMinRole,
  listInvitations,
  listMembers,
  type Invitation,
  type Me,
  type Member,
} from "@/lib/team";

import { TeamClient } from "./team-client";

export const metadata: Metadata = {
  title: "Team — MongoRAG",
  description: "Invite teammates, manage roles, and revoke access.",
};

export const dynamic = "force-dynamic";

export default async function TeamPage() {
  let initialError: string | null = null;
  let me: Me | null = null;
  let members: Member[] = [];
  let invitations: Invitation[] = [];

  try {
    const [meRes, membersRes, invitationsRes] = await Promise.all([
      getMe(),
      listMembers(),
      // Viewer / member don't have access; ignore failures gracefully.
      listInvitations().catch(() => [] as Invitation[]),
    ]);
    me = meRes;
    members = membersRes;
    invitations = invitationsRes;
  } catch (err) {
    initialError =
      err instanceof ApiError
        ? err.message
        : "Could not reach the API. Try again in a moment.";
  }

  const canManage = me ? hasMinRole(me.role, "admin") : false;

  return (
    <div className="mx-auto w-full max-w-5xl space-y-8 px-6 py-10">
      <header className="space-y-1">
        <p className="font-mono text-[0.7rem] tracking-[0.2em] text-muted-foreground uppercase">
          Workspace
        </p>
        <h1 className="font-heading text-2xl leading-tight font-medium tracking-tight">
          Team
        </h1>
        <p className="max-w-xl text-sm text-muted-foreground">
          Invite teammates and decide how much access each of them should have.
          Owners control billing and ownership; admins manage bots, documents,
          and API keys.
        </p>
      </header>

      {initialError ? (
        <div
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive"
        >
          {initialError}
        </div>
      ) : me ? (
        <TeamClient
          me={me}
          canManage={canManage}
          initialMembers={members}
          initialInvitations={invitations}
        />
      ) : null}
    </div>
  );
}
