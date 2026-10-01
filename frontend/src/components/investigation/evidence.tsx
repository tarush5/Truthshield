import { Database, ExternalLink, Search } from 'lucide-react';

import { Badge } from '@/components/ui';
import { cn, formatDate, humanize, safeHref } from '@/lib/format';
import type { ClaimResult, RetrievalDiagnostics, Source, SourceScores } from '@/types/api';

const ASSESSMENT_TONE = {
  SUPPORTED: 'good',
  CONTRADICTED: 'bad',
  MIXED: 'warn',
  INSUFFICIENT_EVIDENCE: 'neutral',
  NOT_CHECKED: 'neutral',
} as const;

const STANCE_TONE = { SUPPORTS: 'good', REFUTES: 'bad', NEUTRAL: 'neutral', OFF_TOPIC: 'neutral' } as const;

const LIVE_LABEL: Record<RetrievalDiagnostics['live_search'], string> = {
  not_needed: 'answered from the evidence store',
  used: 'live search used',
  unavailable: 'live search unavailable',
  failed: 'live search failed',
};

export function ScoreBreakdown({ scores }: { scores: SourceScores }) {
  return (
    <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted" title="Reranker components (0-1) behind the final ordering score">
      <span className="font-mono text-text-primary/80">score {scores.final.toFixed(3)}</span>
      {Object.entries(scores.components).map(([k, v]) => (
        <span key={k} className="tabular">{k} {v.toFixed(2)}</span>
      ))}
      {scores.matched_by.length > 0 && (
        <span>matched by {[...new Set(scores.matched_by.map((m) => m.split(':')[0]))].join(' + ')}</span>
      )}
    </div>
  );
}

export function SourceCard({ source }: { source: Source }) {
  return (
    <li className="rounded-2xl border border-stroke bg-bg p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={STANCE_TONE[source.stance]}>{humanize(source.stance)}</Badge>
        <Badge title="Characteristic of the source, not a guarantee the article is right">{humanize(source.category)}</Badge>
        <span className="text-xs text-muted">credibility {source.credibility.toFixed(2)}</span>
        {source.content_scope && <span className="text-[11px] text-muted">· {source.content_scope === 'snippet' ? 'search snippet' : humanize(source.content_scope)}</span>}
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
      {source.scores && <ScoreBreakdown scores={source.scores} />}
      <p className="mt-2 text-[11px] text-muted/80">
        Retrieved {formatDate(source.retrieved_at)} · Published {source.published_at ? formatDate(source.published_at) : 'date not provided by source'}
        {source.chunk_id && <span className="font-mono"> · chunk {source.chunk_id.slice(0, 8)}</span>}
      </p>
    </li>
  );
}

function RetrievalLine({ r }: { r: RetrievalDiagnostics }) {
  return (
    <div className="mt-4 rounded-2xl border border-stroke bg-bg/60 px-4 py-3 text-xs text-muted">
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="inline-flex items-center gap-1"><Database className="h-3.5 w-3.5" aria-hidden /> {r.local_relevant_before} relevant in store before search</span>
        <span className={cn('inline-flex items-center gap-1', r.live_search === 'failed' && 'text-risk-high')}>
          <Search className="h-3.5 w-3.5" aria-hidden /> {LIVE_LABEL[r.live_search]}
          {r.live_search === 'used' && ` (${r.live_hits} results, ${r.ingested} new)`}
        </span>
        <span>{r.embedding.kind} embeddings</span>
        <span>reranker {r.reranker}</span>
      </p>
      {r.live_detail && <p className="mt-1">{r.live_detail}</p>}
      <details className="mt-1">
        <summary className="cursor-pointer text-text-primary/70">Query variants ({r.query_variants.length})</summary>
        <ul className="mt-1 space-y-0.5">
          {r.query_variants.map((v) => <li key={v.strategy}><span className="text-text-primary/70">{v.strategy}:</span> {v.query}</li>)}
        </ul>
      </details>
    </div>
  );
}

export function ClaimCard({ claim }: { claim: ClaimResult }) {
  const assessment = claim.assessment ?? 'NOT_CHECKED';
  return (
    <article className="rounded-3xl border border-stroke bg-surface/50 p-5">
      <header className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-xs text-muted">{claim.id}</span>
        <Badge tone={ASSESSMENT_TONE[assessment]}>{humanize(assessment)}</Badge>
        {claim.downgraded && <Badge tone="warn" title="Only low-credibility sources supported a decision, so none was made">downgraded</Badge>}
        {claim.confidence !== undefined && claim.confidence !== null && (
          <span className="text-xs text-muted">confidence {claim.confidence.toFixed(2)}</span>
        )}
      </header>
      <p className="mt-3 text-base leading-relaxed text-text-primary">“{claim.text}”</p>
      {claim.reasoning && <p className={cn('mt-2 text-sm', assessment === 'NOT_CHECKED' ? 'text-muted' : 'text-text-primary/80')}>{claim.reasoning}</p>}
      {claim.retrieval && <RetrievalLine r={claim.retrieval} />}
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
