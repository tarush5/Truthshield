import { createClient } from '@supabase/supabase-js';
import { SUPABASE_URL, SUPABASE_ANON_KEY } from '../../config';

let supabaseInstance;

try {
  // Only call createClient if URL and Key are provided and non-empty
  if (SUPABASE_URL && SUPABASE_ANON_KEY && SUPABASE_ANON_KEY.trim() !== '') {
    supabaseInstance = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      auth: {
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: true,
      },
    });
  } else {
    throw new Error("Missing SUPABASE_URL or SUPABASE_ANON_KEY configuration");
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
        alert("Google Sign-In is unavailable because Supabase is not configured. Please use local Sign In or Demo mode.");
        return { data: {}, error: new Error("Supabase is not configured") };
      },
      signInWithPassword: async () => ({ data: {}, error: new Error("Supabase is not configured") }),
      signUp: async () => ({ data: {}, error: new Error("Supabase is not configured") }),
      signOut: async () => ({ error: null }),
    }
  };
}

export const supabase = supabaseInstance;
