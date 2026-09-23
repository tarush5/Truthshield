import React from 'react';
import { Link } from 'react-router-dom';
import { History } from 'lucide-react';

import { getVerdict, toneColor } from '../lib/verdict';

/**
 * Claims this system has ruled on before that resemble this one.
 *
 * Deliberately *below* the verdict and framed as history, never as an
 * answer. Evidence moves: a claim ruled false in March may have a different
 * evidence base today, and presenting a prior verdict as the current one
 * would be a cached answer with a stale date hidden behind it.
 *
 * A near-duplicate is marked as such, because the two thresholds mean
 * genuinely different things — "we have answered this question" and "here is
 * an adjacent one" should not look alike.
 */

function when(iso) {
  if (!iso) return null;
  const then = new Date(iso);
  const days = Math.floor((Date.now() - then.getTime()) / 86_400_000);
  if (days < 1) return 'today';
  if (days === 1) return 'yesterday';
  if (days < 30) return `${days} days ago`;
  return then.toLocaleDateString(undefined, { month: 'short', year: 'numeric' });
}

export default function PriorClaims({ claims = [] }) {
  if (!claims.length) return null;

  const duplicates = claims.filter((c) => c.near_duplicate).length;

  return (
    <section className="card p-5">
      <header className="mb-1 flex items-center gap-2">
        <History className="h-3.5 w-3.5 text-ink-muted" />
        <h2 className="text-sm font-semibold text-ink">Checked before</h2>
      </header>
      <p className="mb-4 text-[0.6875rem] leading-relaxed text-ink-muted">
        {duplicates > 0
          ? 'This closely matches something already checked. The verdict above is from a fresh analysis — evidence changes, so an older ruling is context rather than an answer.'
          : 'Related claims previously checked, for context.'}
      </p>

      <ul className="space-y-2">
        {claims.map((claim) => {
          const meta = getVerdict(claim.verdict);
          return (
            <li key={claim.report_id}>
              <Link
                to={`/report/${claim.report_id}`}
                className="card-hover flex items-start gap-3 rounded-lg border border-line p-3"
              >
                <span
                  className="mt-1 h-2 w-2 shrink-0 rounded-full"
                  style={{ background: toneColor(claim.verdict) }}
                  aria-hidden="true"
                />
                <span className="min-w-0 flex-1">
                  <span className="line-clamp-2 block text-[0.8125rem] leading-snug text-ink-secondary">
                    {claim.text}
                  </span>
                  <span className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[0.6875rem] text-ink-muted">
                    {/* The label carries the verdict, not the colour alone —
                        the dot is a second encoding, not the only one. */}
                    <span className="font-medium">{meta.headline}</span>
                    {claim.created_at && <span>· {when(claim.created_at)}</span>}
                    {claim.near_duplicate && (
                      <span className="rounded border border-line px-1 py-px font-mono">
                        near-duplicate
                      </span>
                    )}
                  </span>
                </span>
                <span className="shrink-0 font-mono text-[0.6875rem] tabular-nums text-ink-muted">
                  {Math.round(claim.similarity * 100)}%
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
