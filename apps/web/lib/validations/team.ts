import { z } from "zod/v3";

export const teamRoles = ["owner", "admin", "member", "viewer"] as const;

export const inviteMemberSchema = z.object({
  email: z.string().email("Enter a valid email"),
  role: z.enum(teamRoles).default("member"),
});

export type InviteMemberFormData = z.infer<typeof inviteMemberSchema>;

export const updateMemberRoleSchema = z.object({
  user_id: z.string().min(1),
  role: z.enum(teamRoles),
});
