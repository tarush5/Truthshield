import { useQuery } from '@tanstack/react-query';
import { ExternalLink } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';

import { Logo } from '@/components/landing/Logo';
import { Badge, Card, CardHeader, EmptyState, Skeleton } from '@/components/ui';
import { humanize, safeHref } from '@/lib/format';
import { legacyService } from '@/services';

interface LegacyEvidence { title: string; url: string; snippet: string; source_domain: string | null; stance: string; credibility_label: string }
interface LegacyClaim { text: string; verdict: string; confidence: number; reasoning: string; evidence: LegacyEvidence[] }
interface LegacyReport {
  verdict: string;
  trust_score: number;
  confidence_band: string;
  summary: string;
  reasons: string[];
  limitations: string[];
  claims: LegacyClaim[];
  original_text: string | null;
  source_url: string | null;
  status?: string;
}

/**
 * Read-only view of a 1.x fact-check report, so every report link and share
 * link handed out before 2.0 keeps working.
 */
export default function LegacyReport({ shared = false }: { shared?: boolean }) {
  const { id, token } = useParams();
  const key = shared ? token! : id!;
  const { data, isLoading, error } = useQuery({
    queryKey: ['legacy', shared, key],
    queryFn: async () => (shared ? legacyService.shared(key) : legacyService.report(key)) as Promise<unknown> as Promise<LegacyReport>,
  });

  const body = isLoading ? (
    <Skeleton className="h-96" />
  ) : error || !data ? (
    <EmptyState title="Report unavailable" body={shared ? 'This share link is invalid or has been revoked.' : 'The report does not exist or is not yours.'} />
  ) : (
    <div className="space-y-6">
      <Card className="p-6">
        <div className="flex flex-wrap items-center gap-3">
          <Badge tone="accent">TruthShield 1.x fact-check</Badge>
          <Badge>{humanize(data.confidence_band)} confidence</Badge>
        </div>
        <p className="mt-4 font-display text-4xl italic text-text-primary">{humanize(data.verdict)}</p>
        <p className="mt-1 text-sm text-muted">Trust score {data.trust_score}/100</p>
        <p className="mt-4 text-sm leading-relaxed text-text-primary/85">{data.summary}</p>
        {data.original_text && <blockquote className="mt-4 border-l-2 border-stroke pl-4 text-sm text-muted">{data.original_text}</blockquote>}
      </Card>
      {data.claims.map((c, i) => (
        <Card key={i}>
          <CardHeader eyebrow={`Claim ${i + 1} · ${humanize(c.verdict)}`} title={`“${c.text}”`} />
          <div className="space-y-3 p-5 pt-3 sm:p-6 sm:pt-3">
            <p className="text-sm text-muted">{c.reasoning}</p>
            <ul className="space-y-2">
              {c.evidence.map((e) => (
                <li key={e.url} className="rounded-2xl border border-stroke p-3">
                  <div className="flex flex-wrap gap-2"><Badge>{humanize(e.stance)}</Badge><Badge>{e.credibility_label}</Badge></div>
                  {safeHref(e.url) ? (
                    <a href={safeHref(e.url)} target="_blank" rel="noreferrer noopener" className="mt-2 inline-flex items-center gap-1 text-sm text-text-primary hover:underline">
                      {e.title} <ExternalLink className="h-3.5 w-3.5 text-muted" aria-hidden />
                    </a>
                  ) : <p className="mt-2 text-sm text-text-primary">{e.title}</p>}
                  <p className="text-xs text-muted">{e.source_domain}</p>
                </li>
              ))}
            </ul>
          </div>
        </Card>
      ))}
      {data.limitations.length > 0 && (
        <Card className="p-6">
          <p className="mb-3 text-[11px] uppercase tracking-[0.25em] text-muted">Limitations</p>
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted">{data.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
        </Card>
      )}
    </div>
  );

  if (!shared) return body;
  return (
    <div className="mx-auto min-h-screen max-w-3xl px-4 py-10">
      <Link to="/" className="mb-8 inline-flex items-center gap-3"><Logo size="sm" /><span className="text-sm">TruthShield</span></Link>
      {body}
      <p className="mt-8 text-xs text-muted">Automated assessment. It can be wrong — check the sources before relying on it.</p>
    </div>
  );
}
