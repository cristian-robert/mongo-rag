import { SignJWT } from "jose";

import { auth } from "@/lib/auth";

const ALG = "HS256";
const TTL_SECONDS = 5 * 60;

/**
 * Mint a short-lived HS256 JWT for the FastAPI backend, signed with NEXTAUTH_SECRET.
 *
 * The backend `_resolve_jwt` only requires a `tenant_id` claim and will reject
 * tokens without it. Tenant identity is taken from the NextAuth session — never
 * from client-supplied data — preserving tenant isolation.
 */
export async function mintBackendToken(): Promise<{
  token: string;
  tenantId: string;
} | null> {
  const session = await auth();
  if (!session?.user?.tenant_id) return null;

  const secret = process.env.NEXTAUTH_SECRET;
  if (!secret) {
    throw new Error(
      "NEXTAUTH_SECRET is not configured — cannot mint backend token",
    );
  }

  const now = Math.floor(Date.now() / 1000);
  const token = await new SignJWT({
    tenant_id: session.user.tenant_id,
    sub: session.user.id,
    role: session.user.role,
    email: session.user.email,
  })
    .setProtectedHeader({ alg: ALG })
    .setIssuedAt(now)
    .setExpirationTime(now + TTL_SECONDS)
    .sign(new TextEncoder().encode(secret));

  return { token, tenantId: session.user.tenant_id };
}
