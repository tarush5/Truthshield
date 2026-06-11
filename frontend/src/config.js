// Central API configuration for TruthShield
//
// IMPORTANT: For deployed environments, set the VITE_API_URL environment variable
// in your hosting platform (Vercel, Netlify, etc.) to point at your backend.
// Example: VITE_API_URL=https://your-backend.onrender.com/api/v1

const resolveApiBase = () => {
  // 1. Always prefer the explicit env var
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }

  // 2. Local development — connect to local backend
  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    return 'http://127.0.0.1:8000/api/v1';
  }

  // 3. Deployed without VITE_API_URL — warn developer and still try local
  console.warn(
    '[TruthShield] VITE_API_URL is not set. The frontend cannot reach the backend API. ' +
    'Set VITE_API_URL in your hosting platform environment variables ' +
    '(e.g. https://your-backend.onrender.com/api/v1).'
  );
  return '/api/v1'; // Will 404 on static hosts — but the error handling will show a clear message
};

export const API_BASE = resolveApiBase();

// Supabase configuration
export const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || 'https://hjlcpxhlmjmyyhixnciu.supabase.co';
export const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || '';

// Dynamic WebSocket URL resolver
export const getWsUrl = () => {
  // Helper: strip any protocol and build a clean ws(s) URL
  const toWs = (raw) => {
    const stripped = raw.replace(/^wss?:\/\//, '').replace(/^https?:\/\//, '');
    const isSecure = raw.startsWith('https:') || raw.startsWith('wss:') || 
                     (!raw.startsWith('http:') && !raw.startsWith('ws:'));
    return `${isSecure ? 'wss' : 'ws'}://${stripped}`;
  };

  if (import.meta.env.VITE_WS_URL) {
    return toWs(import.meta.env.VITE_WS_URL);
  }
  if (import.meta.env.VITE_API_URL) {
    try {
      const url = new URL(import.meta.env.VITE_API_URL);
      const wsProtocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
      return `${wsProtocol}//${url.host}/ws/analyze`;
    } catch {
      // fall through
    }
  }
  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    return 'ws://127.0.0.1:8000/ws/analyze';
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/ws/analyze`;
};

// Helper: check if a fetch error is a backend-unreachable error
export const isBackendError = (error) => {
  if (error instanceof TypeError && error.message.includes('fetch')) return true;
  if (error?.message?.includes('NetworkError')) return true;
  if (error?.message?.includes('Failed to fetch')) return true;
  return false;
};

export const BACKEND_UNREACHABLE_MSG =
  'Cannot reach the TruthShield backend. Please ensure the backend server is running, ' +
  'or set VITE_API_URL in your environment variables.';
