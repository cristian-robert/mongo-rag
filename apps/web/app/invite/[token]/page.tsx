import { notFound } from "next/navigation";

import { getSession } from "@/lib/auth";

import { AcceptInviteClient } from "./accept-invite-client";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8100";

interface InvitePreview {
  email: string;
  role: "owner" | "admin" | "member" | "viewer";
  organization_name: string;
  expires_at: string;
  requires_signup: boolean;
}

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ token: string }>;
}

export default async function InvitePage({ params }: PageProps) {
  const { token } = await params;

  // Server-side preview — non-sensitive, prevents the client from
  // hammering an unknown token endlessly.
  const res = await fetch(
    `${API_URL}/api/v1/team/invitations/${encodeURIComponent(token)}/preview`,
    { cache: "no-store" },
  );
  if (res.status === 404) {
    notFound();
  }
  if (!res.ok) {
    return (
      <main className="flex min-h-svh items-center justify-center px-6">
        <p className="text-sm text-destructive">
          Could not load this invitation. Please try again later.
        </p>
      </main>
    );
  }
  const preview = (await res.json()) as InvitePreview;

  const session = await getSession();
  const signedInEmail = session?.user?.email ?? null;

  return (
    <AcceptInviteClient
      token={token}
      preview={preview}
      signedInEmail={signedInEmail}
    />
  );
}
