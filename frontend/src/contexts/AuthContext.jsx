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
    // Get initial session from localStorage for self-contained local auth
    const token = localStorage.getItem('token');
    const savedUser = localStorage.getItem('user');
    if (token && savedUser) {
      try {
        const parsedUser = JSON.parse(savedUser);
        setSession({ access_token: token });
        setUser(parsedUser);
      } catch (e) {
        console.error('Failed to parse saved user:', e);
        localStorage.removeItem('token');
        localStorage.removeItem('user');
      }
    }
    setLoading(false);
  }, []);

  // Sign in with OTP via backend auth
  const signInWithOtp = useCallback(async (email) => {
    const res = await fetch(`${API_BASE}/auth/otp`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to send OTP');
    }
    return true;
  }, []);

  // Verify OTP via backend auth
  const verifyOtp = useCallback(async (email, token) => {
    const res = await fetch(`${API_BASE}/auth/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, token }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Invalid OTP code');
    }
    const data = await res.json();
    setSession({ access_token: data.access_token });
    setUser(data.user);
    localStorage.setItem('token', data.access_token);
    localStorage.setItem('user', JSON.stringify(data.user));
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

  // Sign up with Password
  const signUpWithPassword = useCallback(async (email, password) => {
    const res = await fetch(`${API_BASE}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Sign up failed');
    }
    const data = await res.json();
    setSession({ access_token: data.access_token });
    setUser(data.user);
    localStorage.setItem('token', data.access_token);
    localStorage.setItem('user', JSON.stringify(data.user));
    return data;
  }, []);

  // Sign in with Password
  const signInWithPassword = useCallback(async (email, password) => {
    const res = await fetch(`${API_BASE}/auth/signin`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Sign in failed');
    }
    const data = await res.json();
    setSession({ access_token: data.access_token });
    setUser(data.user);
    localStorage.setItem('token', data.access_token);
    localStorage.setItem('user', JSON.stringify(data.user));
    return data;
  }, []);

  // Sign in as Demo
  const signInAsDemo = useCallback(async () => {
    const res = await fetch(`${API_BASE}/auth/demo`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Demo login failed');
    }
    const data = await res.json();
    setSession({ access_token: data.access_token });
    setUser(data.user);
    localStorage.setItem('token', data.access_token);
    localStorage.setItem('user', JSON.stringify(data.user));
    return data;
  }, []);

  // Complete OAuth login callback flow
  const completeOAuthLogin = useCallback((token, user) => {
    setSession({ access_token: token });
    setUser(user);
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(user));
  }, []);

  // Sign out
  const signOut = useCallback(async () => {
    try {
      await supabase.auth.signOut();
    } catch (e) {
      // ignore
    }
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

  // Fetch user's organizations (supports array or nested object payload)
  const fetchOrganizations = useCallback(async () => {
    const token = session?.access_token || localStorage.getItem('token');
    if (!token) return [];
    try {
      const res = await fetch(`${API_BASE}/organizations`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return [];
      const data = await res.json();
      return Array.isArray(data) ? data : (data.organizations || []);
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
    signUpWithPassword,
    signInWithPassword,
    signInAsDemo,
    completeOAuthLogin,
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
