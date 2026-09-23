import React, { useState } from 'react';

/**
 * The domains this system actually leans on.
 *
 * Bar length is citation count — the one measure every row shares. The
 * stance split (supports / refutes / neutral) is a *composition* within that
 * length rather than a second axis, because a domain that only ever appears
 * on one side of claims is the interesting finding here and putting it on
 * its own scale would hide the comparison.
 *
 * Credibility is shown as a number, not a second bar. It is a mean, and a
 * mean over three citations is not a rating: rows below the API's sample
 * floor say so instead of showing a figure that invites a decision.
 */

const STANCES = [
  { key: 'refutes', label: 'Refutes', token: 'var(--c-critical)' },
  { key: 'neutral', label: 'Neutral', token: 'var(--c-ink-muted)' },
  { key: 'supports', label: 'Supports', token: 'var(--c-good)' },
];

export default function SourceBars({ sources = [], limit = 10 }) {
  const [hover, setHover] = useState(null);
  const rows = sources.slice(0, limit);

  if (!rows.length) {
    return (
      <div className="flex h-[200px] items-center justify-center text-sm text-ink-muted">
        No sources cited in this window yet.
      </div>
    );
  }

  const max = Math.max(...rows.map((r) => r.citations), 1);

  return (
    <div>
      <div className="space-y-2">
        {rows.map((row) => {
          const width = (row.citations / max) * 100;
          const isHover = hover === row.domain;

          return (
            <div
              key={row.domain}
              className="group grid grid-cols-[minmax(0,10rem)_1fr_auto] items-center gap-3"
              onMouseEnter={() => setHover(row.domain)}
              onMouseLeave={() => setHover(null)}
            >
              <span className="truncate font-mono text-[0.6875rem] text-ink-secondary" title={row.domain}>
                {row.domain}
              </span>

              <div className="relative h-5">
                <div
                  className="flex h-full overflow-hidden rounded-[3px] transition-opacity"
                  style={{ width: `${width}%`, opacity: hover && !isHover ? 0.5 : 1 }}
                >
                  {STANCES.map((stance) => {
                    const value = row[stance.key] || 0;
                    if (!value) return null;
                    return (
                      <span
                        key={stance.key}
                        // 2px surface gap between adjacent fills, so the
                        // segments read as separate quantities rather than
                        // one bar with a colour change in it.
                        className="h-full border-r-2 border-[rgb(var(--c-surface))] last:border-r-0"
                        style={{
                          width: `${(value / row.citations) * 100}%`,
                          background: `rgb(${stance.token})`,
                        }}
                      />
                    );
                  })}
                </div>

                {isHover && (
                  <div className="pointer-events-none absolute left-0 top-6 z-20 whitespace-nowrap rounded-lg border border-line bg-surface-raised px-2.5 py-2 shadow-lg">
                    {STANCES.map((stance) => (
                      <div key={stance.key} className="flex items-center gap-2 py-0.5">
                        <span
                          className="h-2 w-2 rounded-[2px]"
                          style={{ background: `rgb(${stance.token})` }}
                        />
                        <span className="text-[0.6875rem] text-ink-secondary">{stance.label}</span>
                        <span className="ml-2 font-mono text-[0.6875rem] text-ink">
                          {row[stance.key] || 0}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex items-center gap-2.5 tabular-nums">
                <span className="font-mono text-[0.6875rem] text-ink">{row.citations}</span>
                <span
                  className="w-10 text-right font-mono text-[0.6875rem] text-ink-muted"
                  title={
                    row.reliable_sample
                      ? 'Mean credibility of this domain'
                      : 'Too few citations for a meaningful mean'
                  }
                >
                  {row.reliable_sample ? row.credibility.toFixed(2) : '—'}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-line pt-3">
        {STANCES.map((stance) => (
          <span key={stance.key} className="flex items-center gap-1.5">
            <span
              className="h-2 w-2 rounded-[2px]"
              style={{ background: `rgb(${stance.token})` }}
            />
            <span className="text-[0.6875rem] text-ink-secondary">{stance.label}</span>
          </span>
        ))}
        <span className="ml-auto text-[0.6875rem] text-ink-muted">
          citations · mean credibility
        </span>
      </div>
    </div>
  );
}
