import "server-only";

import { getAccessToken, getSession } from "@/lib/auth";

/**
 * Resolve a backend-bound bearer token from the current request's Supabase
 * session.
 *
 * The FastAPI backend (issue #40) verifies Supabase RS256 access tokens via
 * the project's JWKS and joins the matching `profiles` row to derive
 * `tenant_id`. Tenant identity is therefore never client-supplied.
 *
 * Returns null when the user is unauthenticated; callers should treat that
 * as a 401.
 */
export async function mintBackendToken(): Promise<{
  token: string;
  tenantId: string;
} | null> {
  const session = await getSession();
  if (!session?.user?.tenant_id) return null;

  const token = await getAccessToken();
  if (!token) return null;

  return { token, tenantId: session.user.tenant_id };
}
