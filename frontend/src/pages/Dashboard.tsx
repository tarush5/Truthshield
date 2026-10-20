import { Activity, AlertOctagon, Gauge, Timer } from 'lucide-react';
import { useState, type ReactNode } from 'react';

import { AreaChart, BarChart } from '@/components/charts';
import { InvestigationRow } from '@/components/investigation/InvestigationRow';
import { Badge, ButtonLink, Card, CardHeader, EmptyState, ErrorNotice, PageHeader, Skeleton } from '@/components/ui';
import { useDashboard, useHealth } from '@/hooks/queries';
import { RISK_STYLE, cn, formatMs, humanize } from '@/lib/format';
import type { RiskLevel } from '@/types/api';

const WINDOWS = [7, 30, 90];

function Metric({ label, value, note, icon }: { label: string; value: ReactNode; note?: string; icon: ReactNode }) {
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between text-muted">
        <span className="text-[11px] uppercase tracking-[0.2em]">{label}</span>
        {icon}
      </div>
      <p className="mt-3 font-display text-4xl tabular-nums text-text-primary">{value}</p>
      {note && <p className="mt-1 text-xs text-muted">{note}</p>}
    </Card>
  );
}

export default function Dashboard() {
  const [days, setDays] = useState(30);
  const { data, isLoading, error } = useDashboard(days);
  const health = useHealth();

  const windowPicker = (
    <div className="flex rounded-full border border-stroke bg-surface p-1" role="radiogroup" aria-label="Time window">
      {WINDOWS.map((d) => (
        <button
          key={d}
          role="radio"
          aria-checked={days === d}
          onClick={() => setDays(d)}
          className={cn('rounded-full px-3 py-1.5 text-xs', days === d ? 'bg-stroke text-text-primary' : 'text-muted hover:text-text-primary')}
        >
          {d}d
        </button>
      ))}
    </div>
  );

  return (
    <>
      <PageHeader
        eyebrow="Dashboard"
        title={<>Trust <span className="font-display">overview</span></>}
        description={data?.scope === 'all' ? 'All investigations on this deployment (administrator view).' : 'Your investigations. Every figure is computed from stored results.'}
        actions={<>{windowPicker}<ButtonLink to="/app/investigate" size="sm">New investigation</ButtonLink></>}
      />

      {error && <ErrorNotice error={error} className="mb-6" />}

      {isLoading || !data ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-32" />)}</div>
      ) : data.totals.all_time === 0 ? (
        <EmptyState
          title="No investigations yet"
          body="Run a synthetic demo or submit something suspicious. The dashboard fills in from real results — nothing here is placeholder data."
          action={<ButtonLink to="/app/investigate">Start an investigation</ButtonLink>}
        />
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Metric label="Investigations" value={data.totals.investigations} note={`${data.totals.all_time} all time · ${data.totals.in_progress} running`} icon={<Activity className="h-4 w-4" />} />
            <Metric label="High or critical" value={data.risk_levels.HIGH + data.risk_levels.CRITICAL} note={`${data.risk_levels.CRITICAL} critical`} icon={<AlertOctagon className="h-4 w-4" />} />
            <Metric label="Average risk" value={data.average_risk ?? '—'} note="completed investigations" icon={<Gauge className="h-4 w-4" />} />
            <Metric label="Latency p50 / p95" value={<span className="text-3xl">{formatMs(data.latency_ms.p50)}</span>} note={`p95 ${formatMs(data.latency_ms.p95)} · p99 ${formatMs(data.latency_ms.p99)} · n=${data.latency_ms.samples}`} icon={<Timer className="h-4 w-4" />} />
          </div>

          <div className="grid gap-6 xl:grid-cols-3">
            <Card className="xl:col-span-2">
              <CardHeader eyebrow={`Last ${days} days`} title="Investigations per day" />
              <div className="h-64 p-3 pr-5">
                <AreaChart
                  data={data.volume}
                  xKey="date"
                  formatX={(d) => d.slice(5)}
                  label={`Investigations per day, last ${days} days`}
                  series={[
                    { key: 'total', label: 'All', color: '#E8562F', fill: true },
                    { key: 'high_or_critical', label: 'High / critical', color: RISK_STYLE.CRITICAL.hex },
                  ]}
                />
              </div>
            </Card>

            <Card>
              <CardHeader eyebrow="Completed" title="Risk distribution" />
              <div className="h-64 p-3 pr-5">
                <BarChart
                  label="Completed investigations by risk level"
                  data={(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as RiskLevel[]).map((l) => ({ label: RISK_STYLE[l].label, value: data.risk_levels[l], color: RISK_STYLE[l].hex }))}
                />
              </div>
            </Card>
          </div>

          <div className="grid gap-6 xl:grid-cols-3">
            <Card className="xl:col-span-2">
              <CardHeader eyebrow="Recent" title="Latest investigations" action={<ButtonLink to="/app/history" variant="outline" size="sm">View all</ButtonLink>} />
              <div className="space-y-2 p-5 pt-4 sm:p-6 sm:pt-4">
                {data.recent.map((inv) => <InvestigationRow key={inv.id} inv={inv} />)}
              </div>
            </Card>
            <div className="space-y-6">
              <Card>
                <CardHeader eyebrow="Detection categories" title="Most common risk factors" />
                <ul className="space-y-2 p-5 pt-4 sm:p-6 sm:pt-4">
                  {data.top_risk_factors.length ? data.top_risk_factors.map((f) => (
                    <li key={f.code} className="flex items-center justify-between gap-3 text-sm">
                      <span className="truncate text-text-primary/90">{f.title}</span>
                      <span className="font-mono text-xs tabular text-muted">{f.count}</span>
                    </li>
                  )) : <li className="text-sm text-muted">No scoring factors yet.</li>}
                </ul>
                <div className="flex flex-wrap gap-2 border-t border-stroke px-5 py-4 sm:px-6">
                  {Object.entries(data.by_type).map(([t, n]) => <Badge key={t}>{t} · {n}</Badge>)}
                  {Object.entries(data.by_classification).map(([c, n]) => <Badge key={c} tone="accent">{humanize(c)} · {n}</Badge>)}
                </div>
              </Card>
              <Card>
                <CardHeader eyebrow="System health" title="Live capability report" />
                <div className="space-y-2 p-5 pt-4 text-sm sm:p-6 sm:pt-4">
                  {health.data ? (
                    <>
                      <HealthRow label="API" ok={health.data.status === 'ok'} value={health.data.status} />
                      <HealthRow label="Database" ok={health.data.database} value={health.data.database ? 'connected' : 'unreachable'} />
                      <HealthRow label="Task broker" ok={health.data.broker} value={health.data.broker ? 'reachable' : 'unreachable'} />
                      <HealthRow label="Evidence retrieval" ok={health.data.investigations.evidence_retrieval} value={health.data.investigations.evidence_retrieval ? 'enabled' : 'offline'} />
                      <HealthRow label="Page inspection" ok={health.data.investigations.page_fetch} value={health.data.investigations.page_fetch ? 'enabled' : 'disabled'} />
                      <p className="pt-2 text-xs text-muted">Executor: {health.data.investigations.executor} · risk weights {health.data.risk_config_version}</p>
                    </>
                  ) : health.isError ? <p className="text-muted">Health endpoint unreachable.</p> : <Skeleton className="h-24" />}
                </div>
              </Card>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function HealthRow({ label, ok, value }: { label: string; ok: boolean; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted">{label}</span>
      <span className="flex items-center gap-2 text-text-primary/90">
        <span className={cn('h-1.5 w-1.5 rounded-full', ok ? 'bg-emerald-400' : 'bg-risk-medium')} aria-hidden />
        {value}
      </span>
    </div>
  );
}
