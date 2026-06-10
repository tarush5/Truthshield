import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, Shield } from 'lucide-react';

/**
 * OAuth callback handler — exchanges the URL hash/code for a Supabase session.
 * Supabase client's `detectSessionInUrl: true` handles this automatically,
 * so we just wait for the auth state to settle and redirect.
 */
export default function AuthCallback() {
  const navigate = useNavigate();
  const [error, setError] = useState('');

  useEffect(() => {
    // The Supabase client automatically detects the auth tokens in the URL
    // and sets the session. We just need to wait and redirect.
    const timer = setTimeout(() => {
      const token = localStorage.getItem('token');
      if (token) {
        navigate('/login', { replace: true }); // Login will detect auth and go to workspace step
      } else {
        setError('Authentication failed. Please try again.');
        setTimeout(() => navigate('/login', { replace: true }), 2000);
      }
    }, 1500);

    return () => clearTimeout(timer);
  }, [navigate]);

  return (
    <div className="min-h-[calc(100vh-5rem)] flex items-center justify-center">
      <div className="text-center">
        <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-500 to-cyan-500 flex items-center justify-center mx-auto mb-6 shadow-xl shadow-brand-500/25 glow-pulse">
          <Shield className="w-8 h-8 text-white" />
        </div>
        {error ? (
          <p className="text-red-400 text-sm">{error}</p>
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
