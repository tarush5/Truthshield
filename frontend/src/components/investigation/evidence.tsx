import { ExternalLink } from 'lucide-react';

import { Badge } from '@/components/ui';
import { cn, formatDate, humanize, safeHref } from '@/lib/format';
import type { ClaimResult, Source } from '@/types/api';

const ASSESSMENT_TONE = {
  SUPPORTED: 'good',
  CONTRADICTED: 'bad',
  MIXED: 'warn',
  INSUFFICIENT_EVIDENCE: 'neutral',
  NOT_CHECKED: 'neutral',
} as const;

const STANCE_TONE = { SUPPORTS: 'good', REFUTES: 'bad', NEUTRAL: 'neutral', OFF_TOPIC: 'neutral' } as const;

export function SourceCard({ source }: { source: Source }) {
  return (
    <li className="rounded-2xl border border-stroke bg-bg p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={STANCE_TONE[source.stance]}>{humanize(source.stance)}</Badge>
        <Badge title="Characteristic of the source, not a guarantee the article is right">{humanize(source.category)}</Badge>
        <span className="text-xs text-muted">credibility {source.credibility.toFixed(2)}</span>
      </div>
      {/* Retrieved links are untrusted: http(s) only, no referrer, no opener. */}
      {safeHref(source.url) ? (
        <a href={safeHref(source.url)} target="_blank" rel="noreferrer noopener" className="mt-2 inline-flex items-start gap-1.5 text-sm text-text-primary hover:underline">
          {source.title}
          <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted" aria-hidden />
        </a>
      ) : (
        <p className="mt-2 text-sm text-text-primary">{source.title}</p>
      )}
      <p className="mt-0.5 text-xs text-muted">{source.publisher}</p>
      {source.passage && <blockquote className="mt-3 border-l-2 border-stroke pl-3 text-sm text-muted">{source.passage}</blockquote>}
      <p className="mt-3 text-[11px] text-muted/80">
        Retrieved {formatDate(source.retrieved_at)} · Published {source.published_at ? formatDate(source.published_at) : 'date not provided by source'}
      </p>
    </li>
  );
}

export function ClaimCard({ claim }: { claim: ClaimResult }) {
  const assessment = claim.assessment ?? 'NOT_CHECKED';
  return (
    <article className="rounded-3xl border border-stroke bg-surface/50 p-5">
      <header className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-xs text-muted">{claim.id}</span>
        <Badge tone={ASSESSMENT_TONE[assessment]}>{humanize(assessment)}</Badge>
        {claim.confidence !== undefined && claim.confidence !== null && (
          <span className="text-xs text-muted">confidence {claim.confidence.toFixed(2)}</span>
        )}
      </header>
      <p className="mt-3 text-base leading-relaxed text-text-primary">“{claim.text}”</p>
      {claim.reasoning && <p className={cn('mt-2 text-sm', assessment === 'NOT_CHECKED' ? 'text-muted' : 'text-text-primary/80')}>{claim.reasoning}</p>}
      {claim.sources && claim.sources.length > 0 ? (
        <ul className="mt-4 space-y-3">
          {claim.sources.map((s) => <SourceCard key={s.url} source={s} />)}
        </ul>
      ) : (
        <p className="mt-4 text-xs text-muted">
          {assessment === 'NOT_CHECKED' ? 'No sources were retrieved for this claim.' : 'No usable sources were found.'}
        </p>
      )}
    </article>
  );
}
