import { createClient } from "@supabase/supabase-js";

/**
 * Validate and retrieve Supabase environment variables from import.meta.env.
 * Throws a descriptive configuration error if required environment variables
 * are missing, without exposing any key material or sensitive credentials.
 */
function getSupabaseConfig(): { supabaseUrl: string; supabaseKey: string } {
  const supabaseUrl = import.meta.env.VITE_SUPABASE_URL?.trim();
  const supabaseKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY?.trim();

  if (!supabaseUrl) {
    throw new Error(
      "Missing Supabase configuration: VITE_SUPABASE_URL is not set. " +
      "Please define VITE_SUPABASE_URL in frontend/.env.local."
    );
  }

  if (!supabaseKey) {
    throw new Error(
      "Missing Supabase configuration: VITE_SUPABASE_PUBLISHABLE_KEY is not set. " +
      "Please define VITE_SUPABASE_PUBLISHABLE_KEY in frontend/.env.local."
    );
  }

  return { supabaseUrl, supabaseKey };
}

const { supabaseUrl, supabaseKey } = getSupabaseConfig();

/**
 * Reusable Supabase client instance for client-side authentication and queries.
 * Configured with SDK defaults: local session persistence, automatic token
 * refresh, and URL session detection.
 */
export const supabase = createClient(supabaseUrl, supabaseKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
});
