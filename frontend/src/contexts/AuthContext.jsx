import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { api, tokenStore } from '../lib/api';

/**
 * Session state.
 *
 * Restores optimistically from localStorage so the first paint is not a
 * spinner, then confirms with the server. If that confirmation fails the
 * session is cleared — the previous version kept a rejected token in storage
 * and rendered a signed-in shell whose every request 401'd.
 */
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => tokenStore.user());
  const [checking, setChecking] = useState(() => Boolean(tokenStore.get()));

  useEffect(() => {
    if (!tokenStore.get()) return undefined;

    let alive = true;
    api.me()
      .then((me) => { if (alive) setUser(me); })
      .catch(() => {
        if (!alive) return;
        tokenStore.clear();
        setUser(null);
      })
      .finally(() => { if (alive) setChecking(false); });

    return () => { alive = false; };
  }, []);

  const adopt = useCallback((payload) => {
    tokenStore.set(payload.access_token, payload.user);
    setUser(payload.user);
    return payload.user;
  }, []);

  const value = useMemo(() => ({
    user,
    checking,
    isAuthenticated: Boolean(user),
    signIn: async (email, password) => adopt(await api.signin(email, password)),
    signUp: async (email, password) => adopt(await api.signup(email, password)),
    requestOtp: (email) => api.requestOtp(email),
    verifyOtp: async (email, code) => adopt(await api.verifyOtp(email, code)),
    signOut: () => {
      tokenStore.clear();
      setUser(null);
    },
  }), [user, checking, adopt]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside AuthProvider');
  return context;
}
