import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

import type { TokenResponse, User } from '@/types/api';

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
  setSession: (response: TokenResponse) => void;
  setUser: (user: User) => void;
  clear: () => void;
}

/**
 * The session. Persisted to localStorage so a reload stays signed in.
 *
 * Trade-off, documented in docs/FRONTEND.md: localStorage is readable by any
 * script on the origin, so an XSS bug would expose these tokens. Access
 * tokens are short-lived and refresh tokens rotate with reuse detection,
 * which bounds the damage; an httpOnly same-site cookie is the stronger
 * option once the API and app share a site.
 */
export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      setSession: (r) => set({ accessToken: r.access_token, refreshToken: r.refresh_token, user: r.user }),
      setUser: (user) => set({ user }),
      clear: () => set({ accessToken: null, refreshToken: null, user: null }),
    }),
    {
      name: 'ts.session',
      storage: createJSONStorage(() => {
        try {
          return window.localStorage;
        } catch {
          // Private mode or blocked storage: the session simply won't persist.
          return {
            getItem: () => null,
            setItem: () => undefined,
            removeItem: () => undefined,
          };
        }
      }),
    },
  ),
);

export const isSignedIn = () => Boolean(useAuth.getState().accessToken);
