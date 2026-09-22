/**
 * API client.
 *
 * One place that knows the wire format. The previous frontend built fetch
 * calls inline in each page, so an endpoint rename meant hunting through
 * components, error handling differed per call site, and a 401 could leave a
 * stale token in localStorage while the UI pretended to be signed in.
 */

const DEFAULT_BASE = 'http://127.0.0.1:8100/api/v1';

function resolveBase() {
  if (import.meta.env.VITE_API_URL) return import.meta.env.VITE_API_URL;
  const { hostname } = window.location;
  if (hostname === 'localhost' || hostname === '127.0.0.1') return DEFAULT_BASE;
  // Deployed behind the same origin, via a rewrite or reverse proxy.
  return '/api/v1';
}

export const API_BASE = resolveBase();

const TOKEN_KEY = 'ts.token';
const USER_KEY = 'ts.user';

export const tokenStore = {
  get: () => {
    try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
  },
  set: (token, user) => {
    try {
      localStorage.setItem(TOKEN_KEY, token);
      if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
    } catch { /* private mode — the session simply won't persist */ }
  },
  user: () => {
    try { return JSON.parse(localStorage.getItem(USER_KEY) || 'null'); } catch { return null; }
  },
  clear: () => {
    try {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
    } catch { /* nothing to clear */ }
  },
};

/** Thrown for every non-2xx response, carrying the status for the caller. */
export class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }

  get isAuthError() {
    return this.status === 401 || this.status === 403;
  }

  get isOffline() {
    return this.status === 0;
  }
}

function describe(status, body) {
  // FastAPI validation errors arrive as a list of {loc, msg}; surfacing the
  // raw array is what produced "[object Object]" in the old UI.
  if (Array.isArray(body?.detail)) {
    return body.detail.map((d) => d.msg || String(d)).join('; ');
  }
  if (typeof body?.detail === 'string') return body.detail;
  if (status === 0) return 'Cannot reach the server. Check that the backend is running.';
  if (status === 429) return 'Too many requests. Please wait a moment.';
  if (status >= 500) return 'The server ran into a problem. Please try again.';
  return `Request failed (${status}).`;
}

async function request(path, { method = 'GET', body, headers = {}, signal } = {}) {
  const token = tokenStore.get();
  const init = { method, signal, headers: { ...headers } };

  if (token) init.headers.Authorization = `Bearer ${token}`;

  if (body instanceof FormData) {
    // Let the browser set the multipart boundary.
    init.body = body;
  } else if (body !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    throw new ApiError(describe(0), 0, null);
  }

  let payload = null;
  const type = response.headers.get('content-type') || '';
  if (type.includes('application/json')) {
    payload = await response.json().catch(() => null);
  }

  if (!response.ok) {
    // A rejected token is dead: clear it rather than leaving the UI in a
    // signed-in state that fails every subsequent call.
    if (response.status === 401) tokenStore.clear();
    throw new ApiError(describe(response.status, payload), response.status, payload);
  }

  return payload;
}

export const api = {
  signup: (email, password) => request('/auth/signup', { method: 'POST', body: { email, password } }),
  signin: (email, password) => request('/auth/signin', { method: 'POST', body: { email, password } }),
  requestOtp: (email) => request('/auth/otp', { method: 'POST', body: { email } }),
  verifyOtp: (email, code) => request('/auth/otp/verify', { method: 'POST', body: { email, code } }),
  me: () => request('/auth/me'),

  analyze: ({ text, url, file, language = 'en', asyncMode = false, signal }) => {
    const form = new FormData();
    if (text) form.append('text', text);
    if (url) form.append('url', url);
    if (file) form.append('file', file);
    form.append('language', language);
    form.append('async_mode', String(asyncMode));
    return request('/analyze', { method: 'POST', body: form, signal });
  },

  report: (id) => request(`/reports/${id}`),
  reports: (limit = 20) => request(`/reports?limit=${limit}`),
  feedback: (reportId, verdict, comment) =>
    request('/feedback', {
      method: 'POST',
      body: { report_id: reportId, user_verdict: verdict, comment },
    }),

  stats: () => request('/stats'),
  health: () => request('/health'),
};

/**
 * Poll a queued report until it settles.
 *
 * Backs off so a long video analysis does not hammer the API, and gives up
 * rather than polling forever — the old UI had no terminal state and would
 * spin indefinitely if a worker died.
 */
export async function pollReport(id, { onTick, signal, timeoutMs = 300000 } = {}) {
  const started = Date.now();
  let delay = 1000;

  for (;;) {
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
    if (Date.now() - started > timeoutMs) {
      throw new ApiError('This analysis is taking longer than expected.', 408, null);
    }

    const report = await api.report(id);
    onTick?.(report);
    if (report.status !== 'queued' && report.status !== 'running') return report;

    await new Promise((resolve) => setTimeout(resolve, delay));
    delay = Math.min(delay * 1.5, 8000);
  }
}
