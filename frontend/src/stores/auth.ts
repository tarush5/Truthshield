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

// Keep every open tab on the same session. Without this a tab kept the
// refresh token it loaded with: after another tab rotated it, this tab's next
// refresh presented a used token, which the server treats as theft and
// answers by revoking the session everywhere. Signing out in one tab now
// signs out the others too.
if (typeof window !== 'undefined') {
  window.addEventListener('storage', (event) => {
    if (event.key === 'ts.session') void useAuth.persist.rehydrate();
  });
}

export const isSignedIn = () => Boolean(useAuth.getState().accessToken);
