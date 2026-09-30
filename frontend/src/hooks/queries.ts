import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { investigationService, platformService, type ListParams } from '@/services';
import type { InvestigationType } from '@/types/api';

export const keys = {
  investigation: (id: string) => ['investigation', id] as const,
  investigations: (params: ListParams) => ['investigations', params] as const,
  dashboard: (days: number) => ['dashboard', days] as const,
  demos: ['demos'] as const,
  health: ['health'] as const,
  engines: ['engines'] as const,
};

const TERMINAL = new Set(['COMPLETED', 'FAILED']);

/** An investigation, polled every 800 ms until it reaches a terminal state. */
export function useInvestigation(id: string | undefined) {
  return useQuery({
    queryKey: keys.investigation(id ?? ''),
    queryFn: () => investigationService.get(id!),
    enabled: Boolean(id),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && TERMINAL.has(status) ? false : 800;
    },
  });
}

export function useInvestigations(params: ListParams) {
  return useQuery({
    queryKey: keys.investigations(params),
    queryFn: () => investigationService.list(params),
    placeholderData: keepPreviousData,
    refetchInterval: (query) =>
      query.state.data?.items.some((i) => !TERMINAL.has(i.status)) ? 2000 : false,
  });
}

export function useCreateInvestigation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { type?: InvestigationType; content?: string; demo_id?: string }) =>
      investigationService.create(body),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['investigations'] });
      client.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

export function useDeleteInvestigation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => investigationService.remove(id),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['investigations'] });
      client.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

export function useDashboard(days: number) {
  return useQuery({ queryKey: keys.dashboard(days), queryFn: () => platformService.dashboard(days) });
}

export function useDemos() {
  return useQuery({ queryKey: keys.demos, queryFn: platformService.demos, staleTime: Infinity });
}

export function useHealth() {
  return useQuery({ queryKey: keys.health, queryFn: platformService.health, staleTime: 60_000, retry: 0 });
}

export function useEngines() {
  return useQuery({ queryKey: keys.engines, queryFn: platformService.engines, staleTime: 300_000 });
}
