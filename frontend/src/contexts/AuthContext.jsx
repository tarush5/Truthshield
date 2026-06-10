import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { supabase } from '../utils/supabase/client';
import { API_BASE } from '../config';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeOrg, setActiveOrg] = useState(() => ({
    id: localStorage.getItem('active_org_id') || null,
    name: localStorage.getItem('active_org_name') || null,
  }));

  // Initialize auth state
  useEffect(() => {
    // Get initial session
    supabase.auth.getSession().then(({ data: { session: s } }) => {
      setSession(s);
      setUser(s?.user ?? null);
      if (s?.access_token) {
        localStorage.setItem('token', s.access_token);
        localStorage.setItem('user', JSON.stringify({ email: s.user.email, id: s.user.id }));
      }
      setLoading(false);
    });

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, s) => {
      setSession(s);
      setUser(s?.user ?? null);
      if (s?.access_token) {
        localStorage.setItem('token', s.access_token);
        localStorage.setItem('user', JSON.stringify({ email: s.user.email, id: s.user.id }));
      } else {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
      }
    });

    return () => subscription.unsubscribe();
  }, []);

  // Sign in with OTP
  const signInWithOtp = useCallback(async (email) => {
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { shouldCreateUser: true },
    });
    if (error) throw error;
    return true;
  }, []);

  // Verify OTP
  const verifyOtp = useCallback(async (email, token) => {
    const { data, error } = await supabase.auth.verifyOtp({
      email,
      token,
      type: 'email',
    });
    if (error) throw error;
    return data;
  }, []);

  // Sign in with Google
  const signInWithGoogle = useCallback(async () => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
      },
    });
    if (error) throw error;
  }, []);

  // Sign out
  const signOut = useCallback(async () => {
    await supabase.auth.signOut();
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    localStorage.removeItem('active_org_id');
    localStorage.removeItem('active_org_name');
    setUser(null);
    setSession(null);
    setActiveOrg({ id: null, name: null });
  }, []);

  // Get auth header for API calls
  const getAuthHeader = useCallback(() => {
    const token = session?.access_token || localStorage.getItem('token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, [session]);

  // Set active organization
  const setOrganization = useCallback((orgId, orgName) => {
    setActiveOrg({ id: orgId, name: orgName });
    localStorage.setItem('active_org_id', orgId);
    localStorage.setItem('active_org_name', orgName);
  }, []);

  // Fetch user's organizations
  const fetchOrganizations = useCallback(async () => {
    const token = session?.access_token || localStorage.getItem('token');
    if (!token) return [];
    try {
      const res = await fetch(`${API_BASE}/organizations`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return [];
      const data = await res.json();
      return data.organizations || [];
    } catch {
      return [];
    }
  }, [session]);

  // Create workspace
  const createOrganization = useCallback(async (name) => {
    const token = session?.access_token || localStorage.getItem('token');
    const res = await fetch(`${API_BASE}/organizations`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ name }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to create workspace');
    }
    return res.json();
  }, [session]);

  const value = {
    user,
    session,
    loading,
    activeOrg,
    signInWithOtp,
    verifyOtp,
    signInWithGoogle,
    signOut,
    getAuthHeader,
    setOrganization,
    fetchOrganizations,
    createOrganization,
    isAuthenticated: !!session,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
