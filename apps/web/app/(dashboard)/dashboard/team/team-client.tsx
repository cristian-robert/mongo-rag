"use client";

import { Plus, Trash2 } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Invitation, Me, Member, TeamRole } from "@/lib/team";

import {
  inviteMemberAction,
  removeMemberAction,
  revokeInvitationAction,
  updateMemberRoleAction,
} from "./actions";

interface Props {
  me: Me;
  canManage: boolean;
  initialMembers: Member[];
  initialInvitations: Invitation[];
}

const ROLE_LABEL: Record<TeamRole, string> = {
  owner: "Owner",
  admin: "Admin",
  member: "Member",
  viewer: "Viewer",
};

function roleVariant(
  role: TeamRole,
): "default" | "info" | "muted" | "success" | "warning" {
  if (role === "owner") return "success";
  if (role === "admin") return "info";
  if (role === "member") return "default";
  return "muted";
}

function rolesAssignableBy(actorRole: TeamRole): TeamRole[] {
  // Owners can assign any role (including owner); admins cannot grant owner.
  if (actorRole === "owner") return ["owner", "admin", "member", "viewer"];
  if (actorRole === "admin") return ["admin", "member", "viewer"];
  return [];
}

export function TeamClient({
  me,
  canManage,
  initialMembers,
  initialInvitations,
}: Props) {
  const [members, setMembers] = useState(initialMembers);
  const [invitations, setInvitations] = useState(initialInvitations);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<TeamRole>("member");
  const [inviteLink, setInviteLink] = useState<string | null>(null);
  const [removeTarget, setRemoveTarget] = useState<Member | null>(null);
  const [isPending, startTransition] = useTransition();

  const meRole = me.role;
  const assignable = rolesAssignableBy(meRole);
  const pendingInvites = invitations.filter(
    (i) => !i.accepted_at && !i.revoked_at,
  );

  function handleInvite() {
    startTransition(async () => {
      const r = await inviteMemberAction({
        email: inviteEmail,
        role: inviteRole,
      });
      if (!r.ok) {
        toast.error(r.error);
        return;
      }
      setInvitations((prev) => [r.data.invitation, ...prev]);
      setInviteLink(r.data.accept_url);
      setInviteEmail("");
      setInviteRole("member");
      setInviteOpen(false);
    });
  }

  function handleRoleChange(m: Member, newRole: TeamRole) {
    if (m.role === newRole) return;
    startTransition(async () => {
      const r = await updateMemberRoleAction({ user_id: m.id, role: newRole });
      if (!r.ok) {
        toast.error(r.error);
        return;
      }
      setMembers((prev) =>
        prev.map((x) => (x.id === m.id ? { ...x, role: newRole } : x)),
      );
      toast.success(`Updated ${m.email} to ${ROLE_LABEL[newRole]}`);
    });
  }

  function handleRemove() {
    if (!removeTarget) return;
    const target = removeTarget;
    startTransition(async () => {
      const r = await removeMemberAction(target.id);
      if (!r.ok) {
        toast.error(r.error);
        return;
      }
      setMembers((prev) => prev.filter((x) => x.id !== target.id));
      toast.success(`Removed ${target.email}`);
      setRemoveTarget(null);
    });
  }

  function handleRevoke(invitationId: string) {
    startTransition(async () => {
      const r = await revokeInvitationAction(invitationId);
      if (!r.ok) {
        toast.error(r.error);
        return;
      }
      setInvitations((prev) =>
        prev.map((i) =>
          i.id === invitationId
            ? { ...i, revoked_at: new Date().toISOString() }
            : i,
        ),
      );
      toast.success("Invitation revoked");
    });
  }

  return (
    <section className="space-y-10">
      <div className="space-y-4">
        <div className="flex items-end justify-between gap-4">
          <div className="space-y-1">
            <h2 className="font-heading text-lg font-medium">Members</h2>
            <p className="text-sm text-muted-foreground">
              {members.length} {members.length === 1 ? "person" : "people"} on
              this workspace.
            </p>
          </div>
          {canManage ? (
            <Button onClick={() => setInviteOpen(true)} disabled={isPending}>
              <Plus />
              Invite
            </Button>
          ) : null}
        </div>

        <div className="rounded-lg border border-border/60">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Email</TableHead>
                <TableHead>Role</TableHead>
                <TableHead className="w-px text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {members.map((m) => {
                const isSelf = m.id === me.user_id;
                const canEditRole =
                  canManage &&
                  !isSelf &&
                  // admins cannot change owner roles
                  (m.role !== "owner" || meRole === "owner");
                const canRemove =
                  canManage &&
                  !isSelf &&
                  (m.role !== "owner" || meRole === "owner");
                return (
                  <TableRow key={m.id}>
                    <TableCell className="font-medium">
                      {m.email}
                      {isSelf ? (
                        <span className="ml-2 text-xs text-muted-foreground">
                          you
                        </span>
                      ) : null}
                    </TableCell>
                    <TableCell>
                      {canEditRole ? (
                        <Select
                          value={m.role}
                          onValueChange={(v) =>
                            handleRoleChange(m, v as TeamRole)
                          }
                          disabled={isPending}
                        >
                          <SelectTrigger className="w-32">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {assignable.map((r) => (
                              <SelectItem key={r} value={r}>
                                {ROLE_LABEL[r]}
                              </SelectItem>
                            ))}
                            {/* If current role is not assignable by actor, still surface it
                                read-only so the value isn't blank. */}
                            {!assignable.includes(m.role) ? (
                              <SelectItem value={m.role} disabled>
                                {ROLE_LABEL[m.role]}
                              </SelectItem>
                            ) : null}
                          </SelectContent>
                        </Select>
                      ) : (
                        <Badge variant={roleVariant(m.role)}>
                          {ROLE_LABEL[m.role]}
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      {canRemove ? (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setRemoveTarget(m)}
                          disabled={isPending}
                          aria-label={`Remove ${m.email}`}
                        >
                          <Trash2 className="size-4" />
                        </Button>
                      ) : null}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </div>

      {canManage ? (
        <div className="space-y-3">
          <div className="space-y-1">
            <h2 className="font-heading text-lg font-medium">
              Pending invitations
            </h2>
            <p className="text-sm text-muted-foreground">
              People who have been invited but have not joined yet.
            </p>
          </div>
          {pendingInvites.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No pending invitations.
            </p>
          ) : (
            <div className="rounded-lg border border-border/60">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Email</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead>Expires</TableHead>
                    <TableHead className="w-px text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {pendingInvites.map((i) => (
                    <TableRow key={i.id}>
                      <TableCell>{i.email}</TableCell>
                      <TableCell>
                        <Badge variant={roleVariant(i.role)}>
                          {ROLE_LABEL[i.role]}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {new Date(i.expires_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRevoke(i.id)}
                          disabled={isPending}
                        >
                          Revoke
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      ) : null}

      <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Invite teammate</DialogTitle>
            <DialogDescription>
              We&rsquo;ll generate a one-time link they can use to accept.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="invite-email">Email</Label>
              <Input
                id="invite-email"
                type="email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="teammate@example.com"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="invite-role">Role</Label>
              <Select
                value={inviteRole}
                onValueChange={(v) => setInviteRole(v as TeamRole)}
              >
                <SelectTrigger id="invite-role">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {assignable.map((r) => (
                    <SelectItem key={r} value={r}>
                      {ROLE_LABEL[r]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => setInviteOpen(false)}
              disabled={isPending}
            >
              Cancel
            </Button>
            <Button
              onClick={handleInvite}
              disabled={isPending || !inviteEmail}
            >
              Send invitation
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={inviteLink !== null}
        onOpenChange={(o) => {
          if (!o) setInviteLink(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Share this invitation link</DialogTitle>
            <DialogDescription>
              This is the only time this link will be shown. Send it to your
              teammate over a secure channel.
            </DialogDescription>
          </DialogHeader>
          {inviteLink ? (
            <div className="rounded-md border border-border/60 bg-muted/30 px-3 py-2 font-mono text-xs break-all select-all">
              {inviteLink}
            </div>
          ) : null}
          <DialogFooter>
            <Button
              onClick={() => {
                if (inviteLink) {
                  navigator.clipboard.writeText(inviteLink);
                  toast.success("Copied to clipboard");
                }
              }}
            >
              Copy link
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={removeTarget !== null}
        onOpenChange={(o) => {
          if (!o) setRemoveTarget(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove member?</DialogTitle>
            <DialogDescription>
              {removeTarget
                ? `${removeTarget.email} will lose access immediately.`
                : null}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => setRemoveTarget(null)}
              disabled={isPending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleRemove}
              disabled={isPending}
            >
              Remove
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
