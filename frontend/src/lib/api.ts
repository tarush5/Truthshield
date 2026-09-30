/**
 * The only module that knows the wire format.
 *
 * Attaches the bearer token; on a 401 performs one refresh -- shared by every
 * request that hit the 401 concurrently -- and retries once. If the refresh
 * fails the session is cleared, so the UI can never sit "signed in" on a dead
 * token.
 */
import { useAuth } from '@/stores/auth';
import type { ApiErrorBody, TokenResponse } from '@/types/api';

const DEFAULT_BASE = 'http://127.0.0.1:8000/api/v1';

function resolveBase(): string {
  const configured = import.meta.env.VITE_API_URL as string | undefined;
  if (configured) return configured.replace(/\/$/, '');
  if (typeof window !== 'undefined') {
    const { hostname } = window.location;
    if (hostname === 'localhost' || hostname === '127.0.0.1') return DEFAULT_BASE;
  }
  return '/api/v1';
}

export const API_BASE = resolveBase();

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string | null;

  constructor(status: number, code: string, message: string, requestId: string | null = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }

  get isOffline() {
    return this.status === 0;
  }
}

export function describeError(status: number, body: ApiErrorBody | null): { code: string; message: string; requestId: string | null } {
  if (body?.error) {
    return { code: body.error.code, message: body.error.message, requestId: body.error.request_id };
  }
  if (typeof body?.detail === 'string') return { code: `HTTP_${status}`, message: body.detail, requestId: null };
  if (status === 0) return { code: 'OFFLINE', message: 'Cannot reach the TruthShield API. Check that the backend is running.', requestId: null };
  if (status === 429) return { code: 'RATE_LIMITED', message: 'Too many requests. Please wait a moment.', requestId: null };
  if (status >= 500) return { code: 'INTERNAL_ERROR', message: 'The server ran into a problem. Please try again.', requestId: null };
  return { code: `HTTP_${status}`, message: `Request failed (${status}).`, requestId: null };
}

let refreshing: Promise<boolean> | null = null;

/** Single-flight refresh: concurrent 401s share one exchange. */
export function refreshSession(): Promise<boolean> {
  if (refreshing) return refreshing;
  const token = useAuth.getState().refreshToken;
  if (!token) return Promise.resolve(false);

  refreshing = (async () => {
    try {
      const response = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: token }),
      });
      if (!response.ok) {
        useAuth.getState().clear();
        return false;
      }
      useAuth.getState().setSession((await response.json()) as TokenResponse);
      return true;
    } catch {
      return false;
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
  auth?: boolean;
  raw?: boolean;
}

export async function request<T>(path: string, options: RequestOptions = {}, retried = false): Promise<T> {
  const { body, auth = true, raw = false, headers, ...rest } = options;
  const token = useAuth.getState().accessToken;

  const init: RequestInit = {
    ...rest,
    headers: {
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(auth && token ? { Authorization: `Bearer ${token}` } : {}),
      ...(headers as Record<string, string> | undefined),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  };

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch {
    const e = describeError(0, null);
    throw new ApiError(0, e.code, e.message);
  }

  if (response.status === 401 && auth && !retried && useAuth.getState().refreshToken) {
    if (await refreshSession()) return request<T>(path, options, true);
  }

  if (!response.ok) {
    let parsed: ApiErrorBody | null = null;
    try {
      parsed = (await response.json()) as ApiErrorBody;
    } catch {
      /* not JSON */
    }
    if (response.status === 401 && auth) useAuth.getState().clear();
    const e = describeError(response.status, parsed);
    throw new ApiError(response.status, e.code, e.message, e.requestId);
  }

  if (raw) return response as unknown as T;
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string, opts?: RequestOptions) => request<T>(path, { ...opts, method: 'GET' }),
  post: <T>(path: string, body?: unknown, opts?: RequestOptions) => request<T>(path, { ...opts, method: 'POST', body }),
  patch: <T>(path: string, body?: unknown, opts?: RequestOptions) => request<T>(path, { ...opts, method: 'PATCH', body }),
  del: <T>(path: string, opts?: RequestOptions) => request<T>(path, { ...opts, method: 'DELETE' }),
};
