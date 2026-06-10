// Central API configuration for TruthShield
export const API_BASE = import.meta.env.VITE_API_URL || 
  ((window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? 'http://127.0.0.1:8000/api/v1'
    : '/api/v1');

// Supabase configuration
export const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || 'https://hjlcpxhlmjmyyhixnciu.supabase.co';
export const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || '';

// Dynamic WebSocket URL resolver
export const getWsUrl = () => {
  if (import.meta.env.VITE_WS_URL) {
    return import.meta.env.VITE_WS_URL;
  }
  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    return 'ws://127.0.0.1:8000/ws/analyze';
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/ws/analyze`;
};

