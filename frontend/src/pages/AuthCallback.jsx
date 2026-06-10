import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, Shield } from 'lucide-react';
import { supabase } from '../utils/supabase/client';
import { useAuth } from '../contexts/AuthContext';
import { API_BASE } from '../config';

/**
 * OAuth callback handler — exchanges the URL hash/code for a Supabase session
 * and then exchanges it with our local backend for a local JWT.
 */
export default function AuthCallback() {
  const navigate = useNavigate();
  const { completeOAuthLogin } = useAuth();
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;

    async function handleCallback() {
      try {
        // Wait a brief moment for Supabase client to parse the OAuth hash in URL
        await new Promise((resolve) => setTimeout(resolve, 500));
        
        const { data: { session }, error: sessionError } = await supabase.auth.getSession();
        
        if (sessionError) throw sessionError;
        
        if (!session) {
          throw new Error('No active Supabase session found. Please try logging in again.');
        }
        
        // POST to local backend to obtain local JWT
        const response = await fetch(`${API_BASE}/auth/oauth-verify`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: session.user.email,
            supabase_token: session.access_token,
          }),
        });
        
        if (!response.ok) {
          const errData = await response.json().catch(() => ({}));
          throw new Error(errData.detail || 'Failed to verify session with backend.');
        }
        
        const data = await response.json();
        
        if (active) {
          // Sync with context state and localStorage
          completeOAuthLogin(data.access_token, data.user);
          // Go back to login/workspace flow
          navigate('/login', { replace: true });
        }
      } catch (err) {
        console.error('OAuth callback exchange error:', err);
        if (active) {
          setError(err.message || 'Authentication failed. Please try again.');
          setTimeout(() => navigate('/login', { replace: true }), 2500);
        }
      }
    }

    handleCallback();

    return () => {
      active = false;
    };
  }, [navigate, completeOAuthLogin]);

  return (
    <div className="min-h-[calc(100vh-5rem)] flex items-center justify-center">
      <div className="text-center">
        <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-500 to-cyan-500 flex items-center justify-center mx-auto mb-6 shadow-xl shadow-brand-500/25 glow-pulse">
          <Shield className="w-8 h-8 text-white" />
        </div>
        {error ? (
          <p className="text-red-400 text-sm max-w-md mx-auto px-4">{error}</p>
        ) : (
          <>
            <Loader2 className="w-6 h-6 text-brand-400 animate-spin mx-auto mb-3" />
            <p className="text-sm text-white/50">Completing sign in...</p>
          </>
        )}
      </div>
    </div>
  );
}
