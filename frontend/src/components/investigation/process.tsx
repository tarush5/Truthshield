import { CheckCircle2, CircleDashed, Loader2, MinusCircle, XCircle } from 'lucide-react';
import type { ReactElement } from 'react';

import { Badge } from '@/components/ui';
import { PIPELINE_STAGES, STAGE_LABEL, STATUS_LABEL, cn, formatMs } from '@/lib/format';
import type { EngineSummary, InvestigationDetail, TimelineEvent } from '@/types/api';

type StageState = 'done' | 'skipped' | 'failed' | 'running' | 'pending';

function stageStates(inv: InvestigationDetail): Record<string, StageState> {
  const byStage = new Map(inv.timeline.map((e) => [e.stage, e]));
  const states: Record<string, StageState> = {};
  for (const stage of PIPELINE_STAGES) {
    const event = byStage.get(stage);
    if (event) states[stage] = event.status === 'completed' ? 'done' : event.status === 'skipped' ? 'skipped' : 'failed';
    else if (inv.current_stage === stage) states[stage] = 'running';
    else states[stage] = 'pending';
  }
  return states;
}

const ICON: Record<StageState, ReactElement> = {
  done: <CheckCircle2 className="h-4 w-4 text-risk-low" aria-hidden />,
  skipped: <MinusCircle className="h-4 w-4 text-muted" aria-hidden />,
  failed: <XCircle className="h-4 w-4 text-risk-critical" aria-hidden />,
  running: <Loader2 className="h-4 w-4 animate-spin text-[#89AACC]" aria-hidden />,
  pending: <CircleDashed className="h-4 w-4 text-stroke" aria-hidden />,
};

/** Live progress while the pipeline runs. */
export function ProcessingStatus({ inv }: { inv: InvestigationDetail }) {
  const states = stageStates(inv);
  const finished = Object.values(states).filter((s) => s !== 'pending' && s !== 'running').length;
  const pct = Math.round((finished / PIPELINE_STAGES.length) * 100);

  return (
    <div className="rounded-3xl border border-stroke bg-surface/60 p-6" aria-live="polite">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.25em] text-muted">Status</p>
          <p className="mt-1 font-display text-3xl italic text-text-primary">{STATUS_LABEL[inv.status] ?? inv.status}</p>
        </div>
        <span className="font-display text-5xl tabular-nums text-text-primary">{String(pct).padStart(3, '0')}</span>
      </div>
      <div className="mt-4 h-[3px] overflow-hidden rounded-full bg-stroke/60">
        <div className="accent-gradient h-full origin-left transition-transform duration-500" style={{ transform: `scaleX(${pct / 100})`, boxShadow: '0 0 8px rgba(137,170,204,0.35)' }} />
      </div>
      <ol className="mt-6 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {PIPELINE_STAGES.map((stage) => (
          <li key={stage} className={cn('flex items-center gap-2 text-sm', states[stage] === 'pending' ? 'text-muted/60' : 'text-text-primary/90')}>
            {ICON[states[stage]]}
            {STAGE_LABEL[stage]}
          </li>
        ))}
      </ol>
    </div>
  );
}

export function InvestigationTimeline({ events }: { events: TimelineEvent[] }) {
  if (!events.length) return <p className="text-sm text-muted">No stages recorded yet.</p>;
  return (
    <ol className="relative space-y-0">
      {events.map((e, i) => {
        const state: StageState = e.status === 'completed' ? 'done' : e.status === 'skipped' ? 'skipped' : 'failed';
        return (
          <li key={e.seq} className="relative grid grid-cols-[1.5rem_1fr] gap-4 pb-5">
            {i < events.length - 1 && <span className="absolute left-[0.7rem] top-6 h-full w-px bg-stroke" aria-hidden />}
            <span className="relative z-10 mt-0.5 flex h-6 w-6 items-center justify-center rounded-full bg-bg">{ICON[state]}</span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <span className="text-sm font-medium text-text-primary">{STAGE_LABEL[e.stage] ?? e.stage}</span>
                <Badge tone={state === 'done' ? 'good' : state === 'failed' ? 'bad' : 'neutral'}>{e.status}</Badge>
                <span className="text-[11px] text-muted">{e.service}</span>
                <span className="ml-auto font-mono text-[11px] tabular text-muted">{formatMs(e.duration_ms)}</span>
              </div>
              {e.message && <p className="mt-1 text-sm text-muted">{e.message}</p>}
              <p className="mt-1 font-mono text-[10px] text-muted/70">{new Date(e.started_at).toISOString()}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

const ENGINE_LABEL: Record<string, string> = { text: 'NLP analysis', url: 'URL analysis', evidence: 'Evidence retrieval' };

/** Which parts of the system ran -- concise operational facts, no reasoning. */
export function AgentActivityPanel({ engines, timeline }: { engines: EngineSummary[]; timeline: TimelineEvent[] }) {
  const stage = (name: string) => timeline.find((e) => e.stage === name);
  const rows = [
    { label: 'Intake', state: stage('HASHING')?.status === 'completed' ? 'ok' : 'pending', detail: 'validated and hashed' },
    ...engines.map((e) => ({
      label: ENGINE_LABEL[e.name] ?? e.name,
      state: e.status,
      detail: e.status === 'ok' ? `${e.signals} signal${e.signals === 1 ? '' : 's'} · ${formatMs(e.duration_ms)}` : e.detail ?? e.status.replace('_', ' '),
    })),
    { label: 'Risk engine', state: stage('RISK_ENGINE')?.status === 'completed' ? 'ok' : 'pending', detail: stage('RISK_ENGINE')?.message ?? '' },
    { label: 'Report', state: stage('STORAGE')?.status === 'completed' ? 'ok' : 'pending', detail: 'stored' },
  ];

  return (
    <ul className="space-y-2">
      {rows.map((r) => (
        <li key={r.label} className="flex items-start gap-3 text-sm">
          {r.state === 'ok' ? ICON.done : r.state === 'error' ? ICON.failed : r.state === 'pending' ? ICON.pending : ICON.skipped}
          <span className="min-w-0">
            <span className="text-text-primary">{r.label}</span>
            {r.detail && <span className="block text-xs text-muted">{r.detail}</span>}
          </span>
        </li>
      ))}
    </ul>
  );
}
