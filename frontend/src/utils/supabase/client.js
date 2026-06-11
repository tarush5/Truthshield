import { createClient } from '@supabase/supabase-js';
import { SUPABASE_URL, SUPABASE_ANON_KEY } from '../../config';

let supabaseInstance;

try {
  // Validate that SUPABASE_ANON_KEY is a valid JWT (starts with 'eyJ')
  const isValidAnonKey = SUPABASE_ANON_KEY && 
                         SUPABASE_ANON_KEY.trim() !== '' && 
                         SUPABASE_ANON_KEY.startsWith('eyJ');

  if (SUPABASE_ANON_KEY && !SUPABASE_ANON_KEY.startsWith('eyJ')) {
    console.error(
      "[TruthShield] Invalid VITE_SUPABASE_ANON_KEY detected. It starts with '" + 
      SUPABASE_ANON_KEY.substring(0, 15) + 
      "...' but it must be a valid JWT (starting with 'eyJ'). If you are using Clerk, please place the Clerk publishable key in the correct variable, not VITE_SUPABASE_ANON_KEY."
    );
  }

  // Only call createClient if URL and Key are provided and valid
  if (SUPABASE_URL && isValidAnonKey) {
    supabaseInstance = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      auth: {
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: true,
      },
    });
  } else {
    throw new Error("Missing or invalid SUPABASE_URL / SUPABASE_ANON_KEY configuration");
  }
} catch (e) {
  console.warn("Supabase client failed to initialize (usually due to missing env vars). Falling back to mock client:", e.message);
  
  // Provide a safe mock client structure to prevent React from crashing
  supabaseInstance = {
    auth: {
      onAuthStateChange: () => ({
        data: {
          subscription: {
            unsubscribe: () => {}
          }
        }
      }),
      getSession: async () => ({ data: { session: null }, error: null }),
      signInWithOAuth: async () => {
        alert("Google Sign-In is unavailable because Supabase is not configured properly. Make sure you set VITE_SUPABASE_ANON_KEY to a valid JWT key on your hosting dashboard.");
        return { data: {}, error: new Error("Supabase is not configured") };
      },
      signInWithPassword: async () => ({ data: {}, error: new Error("Supabase is not configured") }),
      signUp: async () => ({ data: {}, error: new Error("Supabase is not configured") }),
      signOut: async () => ({ error: null }),
    }
  };
}

export const supabase = supabaseInstance;
