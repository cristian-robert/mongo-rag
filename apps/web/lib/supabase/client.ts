import { createBrowserClient } from "@supabase/ssr";

import type { Database } from "@/types/supabase";

/**
 * Browser-side Supabase client. Reads the publishable key from public env.
 * Use only in client components.
 */
export function createClient() {
  return createBrowserClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
  );
}
