import "server-only";

import { cache } from "react";

import { createClient } from "@/lib/supabase/server";
import type { Database } from "@/types/supabase";

type Profile = Database["public"]["Tables"]["profiles"]["Row"];

export type SessionUser = {
  id: string;
  email: string;
  name: string | null;
  tenant_id: string;
  role: Profile["role"];
};

export type Session = { user: SessionUser } | null;

/**
 * Read the current Supabase session and join the matching profile row.
 *
 * `cache()` deduplicates calls within a single request, so server
 * components and server actions can call this freely.
 *
 * Returns null when:
 *   - no Supabase user is set (anonymous)
 *   - the user has no profile row yet (rare race during signup; the
 *     handle_new_user trigger usually creates one synchronously)
 */
export const getSession = cache(async (): Promise<Session> => {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return null;

  const { data: profile } = await supabase
    .from("profiles")
    .select("id, tenant_id, email, role")
    .eq("id", user.id)
    .maybeSingle();

  if (!profile) return null;

  const metadataName =
    typeof user.user_metadata?.name === "string"
      ? (user.user_metadata.name as string)
      : null;

  return {
    user: {
      id: profile.id,
      email: profile.email,
      name: metadataName,
      tenant_id: profile.tenant_id,
      role: profile.role,
    },
  };
});

/**
 * Convenience: returns the SessionUser or throws if unauthenticated.
 * Use in server actions / RSC where the middleware already enforced auth
 * and an unauthenticated state would be a programming error.
 */
export async function requireSession(): Promise<SessionUser> {
  const session = await getSession();
  if (!session) {
    throw new Error("Not authenticated");
  }
  return session.user;
}

/**
 * Read the Supabase access token (JWT) for forwarding to the FastAPI
 * backend. The backend (issue #40) verifies Supabase RS256 tokens and
 * derives `tenant_id` from the joined `profiles` row.
 */
export async function getAccessToken(): Promise<string | null> {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session?.access_token ?? null;
}
