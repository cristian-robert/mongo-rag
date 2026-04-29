"use client";

/**
 * Root client providers. Supabase Auth manages session state via cookies
 * and the in-browser client's `auth.onAuthStateChange` listener — no
 * React context provider is required. This component is kept as a stable
 * seam for future providers (theme, react-query, etc.).
 */
export function Providers({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
