import { motion } from 'motion/react';

import { Badge } from '@/components/ui';
import { CONFIDENCE_LABEL, FAMILY_LABEL, PROVENANCE_LABEL, RISK_STYLE, cn } from '@/lib/format';
import type { ConfidenceBand, Contribution, Provenance, RiskAssessment, RiskLevel } from '@/types/api';

export function RiskGauge({ score, level, size = 168 }: { score: number; level: RiskLevel; size?: number }) {
  const stroke = 10;
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  const style = RISK_STYLE[level];

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="hsl(var(--stroke))" strokeWidth={stroke} />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={style.hex}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: circumference * (1 - score / 100) }}
          transition={{ duration: 1.2, ease: [0.25, 0.1, 0.25, 1] }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-display text-5xl tabular-nums text-text-primary">{score}</span>
        <span className="text-[11px] text-muted">of 100</span>
        <span className={cn('mt-1 text-xs font-semibold uppercase tracking-[0.2em]', style.text)}>{style.label}</span>
      </div>
    </div>
  );
}

export function RiskLevelBadge({ level }: { level: RiskLevel | null }) {
  if (!level) return <Badge>—</Badge>;
  const style = RISK_STYLE[level];
  return (
    <span className={cn('inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wider', style.text)} style={{ borderColor: `${style.hex}66`, background: `${style.hex}14` }}>
      <span className={cn('h-1.5 w-1.5 rounded-full', style.bg)} aria-hidden />
      {style.label}
    </span>
  );
}

export function ConfidenceBadge({ band, value }: { band: ConfidenceBand | null; value?: number | null }) {
  if (!band) return null;
  const segments = { VERY_LOW: 1, LOW: 2, MODERATE: 3, HIGH: 4 }[band];
  return (
    <span className="inline-flex items-center gap-2 text-xs text-muted" title="How much of the system examined this input and how sure the leading signals are. Separate from risk.">
      <span className="flex gap-0.5" aria-hidden>
        {[1, 2, 3, 4].map((i) => (
          <span key={i} className={cn('h-2.5 w-1 rounded-full', i <= segments ? 'accent-gradient' : 'bg-stroke')} />
        ))}
      </span>
      {CONFIDENCE_LABEL[band]}
      {value !== undefined && value !== null && <span className="tabular text-muted/80">({value.toFixed(2)})</span>}
    </span>
  );
}

export function ProvenanceTag({ provenance }: { provenance: Provenance }) {
  const meta = PROVENANCE_LABEL[provenance];
  const tone = provenance === 'retrieved' ? 'accent' : provenance === 'llm' ? 'warn' : 'neutral';
  return (
    <Badge tone={tone} title={meta.hint}>
      {meta.label}
    </Badge>
  );
}

export function RiskScoreCard({ risk }: { risk: RiskAssessment }) {
  return (
    <div className="flex flex-col items-center gap-6 rounded-3xl border border-stroke bg-surface/60 p-6 sm:flex-row sm:items-center">
      <RiskGauge score={risk.score} level={risk.level} />
      <div className="min-w-0 flex-1 text-center sm:text-left">
        <p className="text-[11px] uppercase tracking-[0.25em] text-muted">Risk score</p>
        <p className="mt-2 text-sm leading-relaxed text-text-primary/85">{risk.represents}</p>
        <div className="mt-4 flex flex-wrap items-center justify-center gap-3 sm:justify-start">
          <ConfidenceBadge band={risk.confidence_band} value={risk.confidence} />
          <span className="text-[11px] text-muted" title="The weights this score was computed with">weights {risk.config.version}</span>
        </div>
      </div>
    </div>
  );
}

export function ContributionRow({ c, max }: { c: Contribution; max: number }) {
  const style = c.severity === 'HIGH' ? 'bg-risk-critical' : c.severity === 'MEDIUM' ? 'bg-risk-high' : 'bg-risk-medium';
  return (
    <li className="grid grid-cols-[3rem_1fr] items-start gap-3 py-3">
      <span className="pt-0.5 text-right font-mono text-sm tabular text-text-primary">+{c.points}</span>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-text-primary">{c.title}</span>
          <ProvenanceTag provenance={c.provenance} />
          <span className="text-[11px] text-muted">{FAMILY_LABEL[c.family] ?? c.family}</span>
        </div>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-stroke/60">
          <motion.div className={cn('h-full rounded-full', style)} initial={{ width: 0 }} animate={{ width: `${max ? (c.points / max) * 100 : 0}%` }} transition={{ duration: 0.8 }} />
        </div>
      </div>
    </li>
  );
}

export function RiskBreakdown({ risk }: { risk: RiskAssessment }) {
  const scoring = risk.contributions.filter((c) => c.points > 0);
  const max = Math.max(1, ...scoring.map((c) => c.points));
  const families = Object.entries(risk.families);

  return (
    <div className="grid gap-6 lg:grid-cols-5">
      <div className="lg:col-span-3">
        <p className="mb-1 text-[11px] uppercase tracking-[0.25em] text-muted">Score contributions</p>
        <p className="mb-2 text-xs text-muted">Points sum exactly to the score of {risk.score}.</p>
        {scoring.length ? (
          <ul className="divide-y divide-stroke">
            {scoring.map((c) => <ContributionRow key={c.code} c={c} max={max} />)}
          </ul>
        ) : (
          <p className="py-6 text-sm text-muted">No signal contributed to the score.</p>
        )}
      </div>
      <div className="lg:col-span-2">
        <p className="mb-3 text-[11px] uppercase tracking-[0.25em] text-muted">Signal families</p>
        <ul className="space-y-2">
          {families.map(([name, f]) => (
            <li key={name} className="flex items-center justify-between gap-3 rounded-2xl border border-stroke px-4 py-2.5">
              <div>
                <p className="text-sm text-text-primary">{FAMILY_LABEL[name] ?? name}</p>
                <p className="text-[11px] text-muted">weight {f.weight}</p>
              </div>
              {f.assessed ? (
                <span className="text-right">
                  <span className="block font-mono text-sm tabular text-text-primary">+{f.points}</span>
                  <span className="text-[11px] text-muted">{f.signals} signal{f.signals === 1 ? '' : 's'}</span>
                </span>
              ) : (
                <Badge title="No engine that covers this family ran on this input. It contributes nothing, which is not the same as clean.">Not assessed</Badge>
              )}
            </li>
          ))}
        </ul>
        {risk.notes.length > 0 && (
          <ul className="mt-4 space-y-1.5">
            {risk.notes.map((n) => (
              <li key={n} className="text-xs leading-relaxed text-muted">• {n}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
