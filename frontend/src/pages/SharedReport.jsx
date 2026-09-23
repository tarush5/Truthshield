import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { AlertTriangle, ExternalLink, Loader2, ShieldCheck } from 'lucide-react';

import GroundedExplanation from '../components/GroundedExplanation';
import TrustGauge from '../components/TrustGauge';
import { api } from '../lib/api';
import { getStance, getVerdict, hostOf } from '../lib/verdict';

/**
 * A shared report, as a stranger sees it.
 *
 * Public and unauthenticated. Two things shape it:
 *
 * Everything shown is what the server chose to send — the payload has no
 * report id, no account, no history. This page cannot leak them because it
 * never receives them.
 *
 * It states its own limits harder than the owner's view does. Someone
 * arriving here followed a link from a person making a point, so the page
 * has to be readable as evidence rather than as a verdict handed down: the
 * sources are listed, the caveats are not collapsed, and it says plainly
 * that a machine produced it.
 */

function Sources({ claims }) {
  const all = claims?.flatMap((c) => c.evidence ?? []) ?? [];
  if (!all.length) return null;

  // Sources that bear on the claim first. Retrieval returns plenty that do
  // not -- a claim about what humans use ten percent of pulls in the
  // Warcraft: Orcs & Humans page -- and listing those first buries the ones
  // a reader came to check. The count of the rest is kept, because silently
  // dropping them would overstate how clean the retrieval was.
  const relevant = all.filter((e) => (e.stance || '').toUpperCase() !== 'OFF_TOPIC');
  const offTopic = all.length - relevant.length;
  const shown = (relevant.length ? relevant : all).slice(0, 12);

  return (
    <section className="card p-5">
      <h2 className="mb-1 text-sm font-semibold text-ink">
        Sources ({relevant.length || all.length})
      </h2>
      {offTopic > 0 && relevant.length > 0 && (
        <p className="mb-3 text-[0.6875rem] text-ink-muted">
          {offTopic} further {offTopic === 1 ? 'result was' : 'results were'} retrieved
          but did not address the claim.
        </p>
      )}

      <ul className="mt-3 space-y-2">
        {shown.map((ev, i) => {
          const stance = getStance(ev.stance);
          const raw = (ev.stance || 'NEUTRAL').toUpperCase();
          const tone = raw === 'SUPPORTS' ? '--c-good'
            : raw === 'REFUTES' ? '--c-critical' : '--c-ink-muted';
          return (
            <li key={`${ev.url}-${i}`} className="flex items-start gap-2.5">
              <span
                className="mt-1.5 h-2 w-2 shrink-0 rounded-full"
                style={{ background: `rgb(var(${tone}))` }}
                aria-hidden="true"
              />
              <a
                href={ev.url}
                target="_blank"
                rel="noopener noreferrer nofollow"
                className="group min-w-0 flex-1"
              >
                <span className="line-clamp-2 block text-[0.8125rem] leading-snug text-ink-secondary group-hover:text-ink">
                  {ev.title || ev.url}
                </span>
                <span className="mt-0.5 flex items-center gap-1 font-mono text-[0.6875rem] text-ink-muted">
                  {hostOf(ev.url)}
                  {/* The stance is written out, never colour alone -- and in
                      the reader-facing wording, not the API's enum. */}
                  <span className="ml-1">· {stance.label.toLowerCase()}</span>
                  <ExternalLink className="h-2.5 w-2.5 opacity-0 transition-opacity group-hover:opacity-100" />
                </span>
              </a>
            </li>
          );
        })}
      </ul>
    </section>
  );
}


export default function SharedReport() {
  const { token } = useParams();
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await api.sharedReport(token);
        if (!cancelled) setReport(data);
      } catch (err) {
        if (!cancelled) {
          setError(
            err.status === 404
              ? 'This link is not valid. It may have been revoked by whoever shared it.'
              : err.message || 'Could not load this report.',
          );
        }
      }
    })();
    return () => { cancelled = true; };
  }, [token]);

  if (error) {
    return (
      <div className="mx-auto max-w-lg px-5 py-16 text-center">
        <AlertTriangle className="mx-auto mb-3 h-6 w-6 text-[rgb(var(--c-warning-text))]" />
        <p className="text-sm text-ink-secondary">{error}</p>
        <Link to="/" className="btn-secondary mt-5 !px-4 !py-2 text-sm">
          Check a claim yourself
        </Link>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-brand" />
      </div>
    );
  }

  const meta = getVerdict(report.verdict);

  return (
    <div className="mx-auto max-w-3xl space-y-5 px-5 sm:px-8">
      <div className="flex items-center gap-2 text-[0.6875rem] text-ink-muted">
        <ShieldCheck className="h-3.5 w-3.5" />
        <span>Shared fact-check · checked {new Date(report.created_at).toLocaleDateString()}</span>
      </div>

      <section className="card p-6 sm:p-8">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-start">
          <TrustGauge
            score={report.trust_score}
            verdict={report.verdict}
            confidenceBand={report.confidence_band}
          />
          <div className="min-w-0 flex-1">
            <p className="text-[0.9375rem] leading-relaxed text-ink-secondary">
              {report.summary || meta.gist}
            </p>
            {report.reasons?.length > 0 && (
              <ul className="mt-4 space-y-1.5">
                {report.reasons.map((reason, i) => (
                  <li key={i} className="flex gap-2 text-[0.8125rem] text-ink-secondary">
                    <span className="text-ink-muted">·</span>
                    {reason}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </section>

      {report.original_text && (
        <section className="card p-5">
          <h2 className="mb-2 text-sm font-semibold text-ink">The claim</h2>
          <p className="whitespace-pre-wrap text-[0.8125rem] leading-relaxed text-ink-secondary">
            {report.original_text}
          </p>
        </section>
      )}

      <GroundedExplanation
        explanation={report.explanation}
        evidence={report.claims?.flatMap((c) => c.evidence ?? []) ?? []}
      />

      <Sources claims={report.claims} />

      {/* Not collapsed, unlike the owner's view. A reader who arrived from
          someone making a point is the reader who most needs to see what
          this check could not establish. */}
      {report.limitations?.length > 0 && (
        <section className="card p-5">
          <h2 className="mb-2 text-sm font-semibold text-ink">What this check could not do</h2>
          <ul className="space-y-1.5">
            {report.limitations.map((item, i) => (
              <li key={i} className="flex gap-2 text-[0.8125rem] text-ink-secondary">
                <span className="text-ink-muted">·</span>
                {item}
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="rounded-xl border border-line p-4">
        <p className="text-[0.6875rem] leading-relaxed text-ink-muted">
          This verdict was produced automatically and can be wrong. It is a
          reading of the sources listed above, not an authority — follow them
          before relying on it.
        </p>
        <Link to="/" className="btn-secondary mt-3 !px-3 !py-1.5 text-sm">
          Check a claim yourself
        </Link>
      </div>
    </div>
  );
}
