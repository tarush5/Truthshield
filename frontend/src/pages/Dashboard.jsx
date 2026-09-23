import React, { useCallback, useEffect, useState } from 'react';
import {
  Activity, AlertTriangle, BarChart3, Gauge, Loader2, RefreshCw, Timer,
} from 'lucide-react';

import SourceBars from '../components/charts/SourceBars';
import VolumeChart from '../components/charts/VolumeChart';
import { api } from '../lib/api';

/**
 * Operational view over what the system has actually done.
 *
 * Every figure here carries the sample it came from. That is the whole
 * design constraint: a young deployment has small numbers, and a dashboard
 * that renders "100% agreement" the same way at n=1 and n=400 invites a
 * decision the data cannot support. Rates below the API's sample floor are
 * shown as unavailable rather than shown small.
 */

const WINDOWS = [
  { days: 7, label: '7d' },
  { days: 30, label: '30d' },
  { days: 90, label: '90d' },
];

function percent(rate) {
  return rate === null || rate === undefined ? '—' : `${Math.round(rate * 100)}%`;
}

function seconds(value) {
  if (value === null || value === undefined) return '—';
  return value < 1 ? `${Math.round(value * 1000)}ms` : `${value.toFixed(1)}s`;
}

/**
 * How old the figures are.
 *
 * The aggregate is cached for a minute, so "just now" would be a small lie
 * on a reload. Saying when it was computed costs one line and means the
 * refresh control has a visible effect rather than appearing to do nothing.
 */
function staleness(iso) {
  if (!iso) return null;
  const age = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (age < 5) return 'just now';
  if (age < 90) return `${age}s ago`;
  return `${Math.round(age / 60)}m ago`;
}

/**
 * A single headline figure.
 *
 * `note` is where the denominator goes. It is not optional decoration —
 * every rate on this page is required to state what it was computed from.
 */
function StatTile({ icon: Icon, label, value, note, tone = 'neutral' }) {
  const toneClass = {
    neutral: 'text-ink',
    good: 'text-[rgb(var(--c-good-text))]',
    warning: 'text-[rgb(var(--c-warning-text))]',
    critical: 'text-[rgb(var(--c-critical-text))]',
  }[tone];

  return (
    <div className="card p-4">
      <div className="mb-2 flex items-center gap-2">
        <Icon className="h-3.5 w-3.5 text-ink-muted" />
        <span className="text-[0.6875rem] font-medium uppercase tracking-wide text-ink-muted">
          {label}
        </span>
      </div>
      <div className={`font-mono text-2xl font-semibold tabular-nums ${toneClass}`}>
        {value}
      </div>
      {note && <div className="mt-1 text-[0.6875rem] text-ink-muted">{note}</div>}
    </div>
  );
}

function Panel({ title, description, children, action }) {
  return (
    <section className="card p-5">
      <header className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-ink">{title}</h2>
          {description && (
            <p className="mt-0.5 max-w-prose text-[0.6875rem] leading-relaxed text-ink-muted">
              {description}
            </p>
          )}
        </div>
        {action}
      </header>
      {children}
    </section>
  );
}

export default function Dashboard() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (window, { quiet = false, fresh = false } = {}) => {
    if (!quiet) setLoading(true);
    try {
      setData(await api.insights(window, { fresh }));
      setError(null);
    } catch (err) {
      setError(err.message || 'Could not load insights.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!cancelled) await load(days);
    })();
    return () => { cancelled = true; };
  }, [days, load]);

  const volume = data?.volume;
  const latency = data?.latency;
  const confidence = data?.confidence;
  const calibration = data?.calibration;

  // Taken from the same aggregate as the abstention counts below rather than
  // summed from the daily buckets. The two disagree at the window edge --
  // buckets are calendar days, the aggregate is a rolling timestamp cut --
  // and two totals differing by four on one screen reads as a broken number
  // whichever of them is "right".
  const analysed = confidence?.total ?? 0;

  // Abstention is the number to watch: it going up means retrieval is
  // finding less usable evidence, which a verdict breakdown hides by
  // treating "unverified" as just another outcome.
  //
  // No green step. A low abstention rate is not a success -- the system
  // could be committing confidently and wrongly -- and colouring it good
  // would assert something this figure cannot show on its own.
  const abstention = confidence?.abstention_rate;
  const abstentionTone =
    abstention === null || abstention === undefined ? 'neutral'
      : abstention > 0.45 ? 'critical'
        : abstention > 0.25 ? 'warning' : 'neutral';

  return (
    <div className="mx-auto max-w-5xl px-5 sm:px-8">
      <header className="mb-7 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl tracking-tight text-ink">Insights</h1>
          <p className="mt-1 text-sm text-ink-muted">
            What this system has checked, which sources it leaned on, and where
            readers disagreed with it.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-line p-0.5" role="group" aria-label="Time window">
            {WINDOWS.map((w) => (
              <button
                key={w.days}
                onClick={() => setDays(w.days)}
                aria-pressed={days === w.days}
                className={`rounded-md px-2.5 py-1 font-mono text-[0.6875rem] transition-colors ${
                  days === w.days
                    ? 'bg-brand/12 text-brand'
                    : 'text-ink-muted hover:text-ink'
                }`}
              >
                {w.label}
              </button>
            ))}
          </div>
          <button
            onClick={() => load(days, { quiet: true, fresh: true })}
            className="btn-ghost !p-2"
            aria-label="Refresh"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </header>

      {error && (
        <div className="mb-6 flex items-start gap-2.5 rounded-xl border border-[rgb(var(--c-critical))]/30 bg-[rgb(var(--c-critical))]/[0.07] p-3.5">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[rgb(var(--c-critical-text))]" />
          <p className="text-sm text-ink-secondary">{error}</p>
        </div>
      )}

      {loading && !data ? (
        <div className="flex min-h-[40vh] items-center justify-center">
          <Loader2 className="h-5 w-5 animate-spin text-brand" />
        </div>
      ) : (
        <div className="space-y-5">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile
              icon={BarChart3}
              label="Analysed"
              value={analysed.toLocaleString()}
              note={`completed in ${days} days`}
            />
            <StatTile
              icon={Gauge}
              label="Abstained"
              value={percent(abstention)}
              note={
                confidence?.total
                  ? `${confidence.abstentions} of ${confidence.total}`
                  : 'no analyses yet'
              }
              tone={abstentionTone}
            />
            <StatTile
              icon={Timer}
              label="Median time"
              value={seconds(latency?.p50)}
              note={latency?.count ? `p95 ${seconds(latency.p95)}` : 'no samples'}
            />
            <StatTile
              icon={Activity}
              label="Reader agreement"
              value={
                calibration?.reliable_sample ? percent(calibration.agreement_rate) : '—'
              }
              note={
                calibration?.feedback_count
                  ? `${calibration.feedback_count} response${calibration.feedback_count === 1 ? '' : 's'}`
                  : 'no feedback yet'
              }
            />
          </div>

          <Panel
            title="Volume by verdict"
            description="Daily counts. Quiet days are drawn as zero rather than skipped, so the line never interpolates across a gap."
          >
            <VolumeChart data={volume} />
          </Panel>

          <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
            <Panel
              title="Sources relied on"
              description="Bar length is citations; the split within it is how that domain's evidence fell. Credibility is a mean, shown only where there are enough citations to mean something."
            >
              <SourceBars sources={data?.sources?.sources ?? []} />
            </Panel>

            <Panel
              title="Where readers disagreed"
              description="Self-selected feedback — people who disagree are likelier to leave it. Read it as a prompt to investigate, not as an accuracy score."
            >
              {calibration?.by_verdict?.length ? (
                <div className="space-y-2.5">
                  {calibration.by_verdict.map((row) => (
                    <div key={row.verdict} className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate text-[0.8125rem] text-ink-secondary">
                          {row.verdict}
                        </div>
                        <div className="text-[0.6875rem] text-ink-muted">
                          {row.agreed} agreed · {row.disagreed} disagreed
                        </div>
                      </div>
                      <span
                        className="shrink-0 font-mono text-sm tabular-nums text-ink"
                        title={
                          row.reliable_sample
                            ? undefined
                            : 'Too few responses to compute a meaningful rate'
                        }
                      >
                        {row.reliable_sample ? percent(row.agreement_rate) : '—'}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="py-8 text-center text-sm text-ink-muted">
                  No reader feedback in this window.
                </p>
              )}
            </Panel>
          </div>

          <p className="pb-2 text-[0.6875rem] leading-relaxed text-ink-muted">
            Figures cover the trailing {days} days and exclude analyses that
            failed. Rates are shown as unavailable rather than rounded where
            the sample is too small to support one.
            {data?.computed_at && (
              <> Computed {staleness(data.computed_at)}; refresh recalculates.</>
            )}
          </p>
        </div>
      )}
    </div>
  );
}
