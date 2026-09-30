import { AlertTriangle, CheckCircle2, HelpCircle, ShieldAlert } from 'lucide-react';

import { ProvenanceTag } from '@/components/investigation/risk';
import { Badge } from '@/components/ui';
import { FAMILY_LABEL, cn, humanize } from '@/lib/format';
import type { Guidance, Signal } from '@/types/api';

const SEVERITY_TONE: Record<string, string> = {
  HIGH: 'border-l-risk-critical',
  MEDIUM: 'border-l-risk-high',
  LOW: 'border-l-risk-medium',
  INFO: 'border-l-stroke',
};

export function SignalCard({ signal }: { signal: Signal }) {
  return (
    <article className={cn('rounded-2xl border border-l-2 border-stroke bg-surface/50 p-4', SEVERITY_TONE[signal.severity])}>
      <header className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-medium text-text-primary">{signal.title}</h3>
        {signal.points > 0 ? (
          <span className="font-mono text-xs tabular text-text-primary">+{signal.points}</span>
        ) : (
          <Badge>{signal.severity === 'INFO' ? 'Informational' : 'No points'}</Badge>
        )}
        <span className="ml-auto flex flex-wrap items-center gap-2">
          <ProvenanceTag provenance={signal.provenance} />
          <Badge>{FAMILY_LABEL[signal.family] ?? signal.family}</Badge>
        </span>
      </header>
      <p className="mt-2 text-sm leading-relaxed text-muted">{signal.explanation}</p>
      {signal.evidence && (
        <p className="mt-3 rounded-xl border border-stroke bg-bg px-3 py-2 font-mono text-xs text-text-primary/90">
          <span className="mr-2 text-[10px] uppercase tracking-wider text-muted">Evidence</span>
          {signal.evidence}
        </p>
      )}
      <footer className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted">
        <span>Severity {humanize(signal.severity)}</span>
        <span>Confidence {signal.confidence.toFixed(2)}</span>
        <span>
          {signal.engine} {signal.engine_version}
        </span>
        <span className="font-mono">{signal.code}</span>
      </footer>
    </article>
  );
}

export function UncertaintyList({ items }: { items: string[] }) {
  if (!items.length) return null;
  return (
    <ul className="space-y-2">
      {items.map((item) => (
        <li key={item} className="flex gap-3 text-sm leading-relaxed text-muted">
          <HelpCircle className="mt-0.5 h-4 w-4 shrink-0 text-[#89AACC]" aria-hidden />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

export function GuidanceCard({ guidance }: { guidance: Guidance }) {
  return (
    <div className="space-y-4">
      <p className="flex items-start gap-3 text-base font-medium text-text-primary">
        <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-[#89AACC]" aria-hidden />
        {guidance.headline}
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        {guidance.do_now.length > 0 && (
          <div>
            <p className="mb-2 text-[11px] uppercase tracking-[0.2em] text-muted">Do now</p>
            <ul className="space-y-1.5">
              {guidance.do_now.map((d) => (
                <li key={d} className="flex gap-2 text-sm text-text-primary/85"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-risk-low" aria-hidden />{d}</li>
              ))}
            </ul>
          </div>
        )}
        {guidance.do_not.length > 0 && (
          <div>
            <p className="mb-2 text-[11px] uppercase tracking-[0.2em] text-muted">Do not</p>
            <ul className="space-y-1.5">
              {guidance.do_not.map((d) => (
                <li key={d} className="flex gap-2 text-sm text-text-primary/85"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-risk-high" aria-hidden />{d}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
      {guidance.if_already_acted.length > 0 && (
        <details className="rounded-2xl border border-stroke px-4 py-3">
          <summary className="cursor-pointer text-sm text-text-primary">If you already clicked, replied or paid</summary>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-muted">
            {guidance.if_already_acted.map((d) => <li key={d}>{d}</li>)}
          </ul>
        </details>
      )}
      {guidance.verify_how && <p className="text-xs text-muted">How to verify: {guidance.verify_how}</p>}
    </div>
  );
}

export function EntityList({ entities }: { entities: Record<string, string[]> }) {
  const entries = Object.entries(entities).filter(([, v]) => v.length);
  if (!entries.length) return <p className="text-sm text-muted">No entities extracted.</p>;
  return (
    <dl className="grid gap-3 sm:grid-cols-2">
      {entries.map(([kind, values]) => (
        <div key={kind} className="rounded-2xl border border-stroke px-4 py-3">
          <dt className="text-[11px] uppercase tracking-[0.2em] text-muted">{humanize(kind)}</dt>
          <dd className="mt-2 flex flex-wrap gap-1.5">
            {values.map((v) => (
              <span key={v} className="break-all rounded-full bg-stroke/60 px-2.5 py-0.5 font-mono text-xs text-text-primary/90">{v}</span>
            ))}
          </dd>
        </div>
      ))}
    </dl>
  );
}
