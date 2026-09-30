// Typed calls per resource. Components never build URLs.
import { api, request } from '@/lib/api';
import type {
  DashboardSummary, DemoCatalogue, EngineInfo, InvestigationDetail, InvestigationSummary,
  InvestigationType, Page, SystemHealth, TimelineEvent, TokenResponse, User,
} from '@/types/api';

export const authService = {
  signin: (email: string, password: string) =>
    api.post<TokenResponse>('/auth/signin', { email, password }, { auth: false }),
  signup: (email: string, password: string) =>
    api.post<TokenResponse>('/auth/signup', { email, password }, { auth: false }),
  logout: (refresh_token: string) => api.post<void>('/auth/logout', { refresh_token }, { auth: false }),
  me: () => api.get<User>('/auth/me'),
};

export interface ListParams {
  q?: string;
  status?: string;
  risk_level?: string;
  type?: string;
  sort?: string;
  page?: number;
  page_size?: number;
}

const query = (params: object) => {
  const search = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') search.set(k, String(v));
  }
  const s = search.toString();
  return s ? `?${s}` : '';
};

export const investigationService = {
  create: (body: { type?: InvestigationType; content?: string; demo_id?: string }) =>
    api.post<{ id: string; public_id: string; status: string; executor: string }>('/investigations', body),
  list: (params: ListParams) => api.get<Page<InvestigationSummary>>(`/investigations${query(params)}`),
  get: (id: string) => api.get<InvestigationDetail>(`/investigations/${encodeURIComponent(id)}`),
  events: (id: string) =>
    api.get<{ status: string; current_stage: string | null; events: TimelineEvent[] }>(`/investigations/${encodeURIComponent(id)}/events`),
  remove: (id: string) => api.del<void>(`/investigations/${encodeURIComponent(id)}`),
  exportFile: async (id: string, format: 'json' | 'csv') => {
    const response = await request<Response>(`/investigations/${encodeURIComponent(id)}/export?format=${format}`, { raw: true });
    return response.blob();
  },
};

export const platformService = {
  dashboard: (days = 30) => api.get<DashboardSummary>(`/dashboard/summary?days=${days}`),
  engines: () => api.get<{ engines: EngineInfo[]; risk: { version: string; weights: Record<string, number> } }>('/engines'),
  demos: () => api.get<DemoCatalogue>('/demo/samples', { auth: false }),
  health: () => api.get<SystemHealth>('/system/health', { auth: false }),
};

export const legacyService = {
  report: (id: string) => api.get<Record<string, unknown>>(`/reports/${encodeURIComponent(id)}`),
  shared: (token: string) => api.get<Record<string, unknown>>(`/shared/${encodeURIComponent(token)}`, { auth: false }),
};
