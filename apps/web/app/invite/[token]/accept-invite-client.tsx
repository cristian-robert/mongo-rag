"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { useState } from "react";
import { toast } from "sonner";

import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8100";

interface InvitePreview {
  email: string;
  role: "owner" | "admin" | "member" | "viewer";
  organization_name: string;
  expires_at: string;
  requires_signup: boolean;
}

interface Props {
  token: string;
  preview: InvitePreview;
  signedInEmail: string | null;
}

const ROLE_LABEL: Record<InvitePreview["role"], string> = {
  owner: "Owner",
  admin: "Admin",
  member: "Member",
  viewer: "Viewer",
};

export function AcceptInviteClient({ token, preview, signedInEmail }: Props) {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");

  const emailMismatch =
    signedInEmail !== null &&
    signedInEmail.toLowerCase() !== preview.email.toLowerCase();

  async function acceptAsExistingUser() {
    setIsLoading(true);
    try {
      const res = await fetch(`/api/invite/${encodeURIComponent(token)}/accept`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      if (!res.ok) {
        const data = (await res.json().catch(() => ({}))) as { detail?: string };
        toast.error(data.detail ?? "Could not accept invitation");
        return;
      }
      toast.success("Welcome to the team");
      router.push("/dashboard");
      router.refresh();
    } finally {
      setIsLoading(false);
    }
  }

  async function acceptAsNewUser() {
    if (password.length < 8) {
      toast.error("Password must be at least 8 characters");
      return;
    }
    setIsLoading(true);
    try {
      const res = await fetch(
        `${API_URL}/api/v1/team/invitations/${encodeURIComponent(token)}/accept-signup`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token, password, name }),
        },
      );
      if (!res.ok) {
        const data = (await res.json().catch(() => ({}))) as { detail?: string };
        toast.error(data.detail ?? "Could not accept invitation");
        return;
      }
      const supabase = createClient();
      const { error: signinError } = await supabase.auth.signInWithPassword({
        email: preview.email,
        password,
      });
      if (signinError) {
        toast.error("Account created but sign-in failed; please log in");
        router.push("/login");
        return;
      }
      toast.success("Welcome to the team");
      router.push("/dashboard");
      router.refresh();
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="flex min-h-svh items-center justify-center px-6 py-12">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Join {preview.organization_name || "the team"}</CardTitle>
          <CardDescription>
            You&rsquo;ve been invited to join as a{" "}
            <strong>{ROLE_LABEL[preview.role]}</strong>. The invitation was
            issued to <strong>{preview.email}</strong>.
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          {emailMismatch ? (
            <div
              role="alert"
              className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive"
            >
              You&rsquo;re signed in as {signedInEmail}. Sign out and accept
              with {preview.email} to continue.
            </div>
          ) : signedInEmail !== null ? (
            <p className="text-sm text-muted-foreground">
              You&rsquo;re already signed in as {signedInEmail}. Accepting will
              move your account to this workspace.
            </p>
          ) : preview.requires_signup ? (
            <>
              <div className="space-y-2">
                <Label htmlFor="invite-name">Your name</Label>
                <Input
                  id="invite-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Alex Doe"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="invite-password">Choose a password</Label>
                <Input
                  id="invite-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 8 characters"
                />
              </div>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              An account already exists for {preview.email}.{" "}
              <Link href="/login" className="underline">
                Sign in
              </Link>{" "}
              to accept this invitation.
            </p>
          )}
        </CardContent>

        <CardFooter className="flex justify-end gap-2">
          {emailMismatch ? (
            <Link
              href="/login"
              className={cn(buttonVariants({ variant: "outline" }))}
            >
              Switch account
            </Link>
          ) : signedInEmail !== null ? (
            <Button onClick={acceptAsExistingUser} disabled={isLoading}>
              Accept invitation
            </Button>
          ) : preview.requires_signup ? (
            <Button onClick={acceptAsNewUser} disabled={isLoading}>
              Create account &amp; join
            </Button>
          ) : null}
        </CardFooter>
      </Card>
    </main>
  );
}
