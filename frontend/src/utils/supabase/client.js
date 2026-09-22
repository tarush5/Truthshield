import { SUPABASE_URL, SUPABASE_ANON_KEY } from '../../config';

/**
 * Supabase client, loaded on demand.
 *
 * This module used to import `@supabase/supabase-js` at the top level, and
 * AuthContext imports this module, and AuthProvider wraps the whole app — so
 * the 211 kB SDK (54 kB gzipped) sat on the critical path of every page load,
 * including the landing page for a signed-out visitor. It is only ever needed
 * for OAuth sign-in and for reacting to an OAuth redirect; day-to-day auth in
 * this app runs on a local JWT in localStorage and never touches Supabase.
 *
 * The SDK is now behind a dynamic import, so it downloads the first time
 * something actually asks for it. The mock below keeps the same shape for the
 * unconfigured case, which is what local development runs in.
 */

const mockClient = {
  auth: {
    onAuthStateChange: () => ({
      data: { subscription: { unsubscribe: () => {} } },
    }),
    getSession: async () => ({ data: { session: null }, error: null }),
    signInWithOAuth: async (args) => {
      const provider = args?.provider || 'google';
      const redirectTo = args?.options?.redirectTo || `${window.location.origin}/auth/callback`;
      localStorage.setItem('oauth_mock_provider', provider);
      window.location.href = redirectTo;
      return { data: { provider }, error: null };
    },
    signInWithPassword: async () => ({ data: {}, error: new Error('Supabase is not configured') }),
    signUp: async () => ({ data: {}, error: new Error('Supabase is not configured') }),
    signOut: async () => ({ error: null }),
  },
};

const isConfigured = Boolean(
  SUPABASE_URL && SUPABASE_ANON_KEY && SUPABASE_ANON_KEY.trim() && SUPABASE_ANON_KEY.startsWith('eyJ')
);

if (SUPABASE_ANON_KEY && !SUPABASE_ANON_KEY.startsWith('eyJ')) {
  console.error(
    "[TruthShield] Invalid VITE_SUPABASE_ANON_KEY detected. It starts with '" +
      SUPABASE_ANON_KEY.substring(0, 15) +
      "...' but it must be a valid JWT (starting with 'eyJ'). If you are using Clerk, " +
      'please place the Clerk publishable key in the correct variable, not VITE_SUPABASE_ANON_KEY.'
  );
}

/** True when real Supabase credentials are present. */
export const supabaseConfigured = isConfigured;

let clientPromise = null;

/**
 * Resolve the Supabase client, downloading the SDK on first call.
 * Returns the mock when credentials are absent, so callers never branch.
 */
export function getSupabase() {
  if (!isConfigured) return Promise.resolve(mockClient);
  if (!clientPromise) {
    clientPromise = import('@supabase/supabase-js')
      .then(({ createClient }) =>
        createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
          auth: {
            autoRefreshToken: true,
            persistSession: true,
            detectSessionInUrl: true,
          },
        })
      )
      .catch((e) => {
        console.warn('Supabase client failed to load; using mock client:', e.message);
        return mockClient;
      });
  }
  return clientPromise;
}
