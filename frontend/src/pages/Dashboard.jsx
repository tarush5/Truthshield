import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Activity, BarChart3, Gauge, RefreshCw, Timer } from 'lucide-react';

import SourceBars from '../components/charts/SourceBars';
import VolumeChart from '../components/charts/VolumeChart';
import {
  EmptyState, InlineError, PageHeader, Section, Skeleton, SkeletonCard,
  StatCard, Tooltip,
} from '../components/ui';
import { api } from '../lib/api';

/**
 * Operational view over what the system has actually done.
 *
 * Every figure carries the sample it came from. That is the design
 * constraint the whole page is built around: a young deployment has small
 * numbers, and a dashboard that renders "100% agreement" identically at
 * n=1 and n=400 invites a decision the data cannot support. Rates below the
 * API's sample floor read as unavailable rather than as small.
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
 * on a reload. Saying when it was computed costs one line and gives the
 * refresh control a visible effect rather than appearing to do nothing.
 */
function staleness(iso) {
  if (!iso) return null;
  const age = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (age < 5) return 'just now';
  if (age < 90) return `${age}s ago`;
  return `${Math.round(age / 60)}m ago`;
}

/**
 * Change between the first and second half of the window.
 *
 * Deliberately crude, and suppressed on thin data: a percentage swing
 * computed from three analyses is noise wearing the costume of a trend.
 */
function halfOverHalf(series, key = 'total') {
  if (!series || series.length < 6) return undefined;
  const mid = Math.floor(series.length / 2);
  const sum = (rows) => rows.reduce((t, r) => t + (r[key] || 0), 0);

  const earlier = sum(series.slice(0, mid));
  const later = sum(series.slice(mid));
  if (earlier < 5) return undefined;
  return ((later - earlier) / earlier) * 100;
}

function LoadingPanels() {
  return (
    <div className="space-y-5" role="status" aria-busy="true" aria-live="polite">
      <span className="sr-only">Loading insights</span>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
      </div>
      <div className="card p-5">
        <Skeleton className="mb-4 h-4 w-40" />
        <Skeleton className="h-[240px] w-full" />
      </div>
      <div className="grid gap-5 xl:grid-cols-[1.4fr_1fr]">
        <div className="card p-5"><Skeleton className="h-[220px] w-full" /></div>
        <div className="card p-5"><Skeleton className="h-[220px] w-full" /></div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (window, { quiet = false, fresh = false } = {}) => {
    if (quiet) setRefreshing(true); else setLoading(true);
    try {
      setData(await api.insights(window, { fresh }));
      setError(null);
    } catch (err) {
      setError(err.message || 'Could not load insights.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(days); }, [days, load]);

  const volume = data?.volume;
  const latency = data?.latency;
  const confidence = data?.confidence;
  const calibration = data?.calibration;

  // Taken from the same aggregate as the abstention counts rather than
  // summed from the daily buckets. The two disagree at the window edge --
  // buckets are calendar days, the aggregate is a rolling timestamp cut --
  // and two totals differing by four on one screen reads as a broken number
  // whichever of them is right.
  const analysed = confidence?.total ?? 0;
  const abstention = confidence?.abstention_rate;

  // No green step. A low abstention rate is not a success -- the system
  // could be committing confidently and wrongly -- and colouring it good
  // would assert something this figure cannot show on its own.
  const abstentionTone =
    abstention === null || abstention === undefined ? 'neutral'
      : abstention > 0.45 ? 'critical'
        : abstention > 0.25 ? 'warning' : 'neutral';

  const spark = useMemo(() => volume?.series?.map((row) => row.total) ?? [], [volume]);
  const volumeTrend = useMemo(() => halfOverHalf(volume?.series), [volume]);

  const hasAnything = analysed > 0;

  return (
    <div className="mx-auto w-full max-w-6xl px-5 sm:px-8">
      <PageHeader
        eyebrow="Operations"
        title="Insights"
        description="What this system has checked, which sources it leaned on, and where readers disagreed with it."
        actions={
          <>
            <div className="flex rounded-xl border border-line p-0.5" role="group" aria-label="Time window">
              {WINDOWS.map((w) => (
                <button
                  key={w.days}
                  onClick={() => setDays(w.days)}
                  aria-pressed={days === w.days}
                  className={`focusable rounded-lg px-2.5 py-1 font-mono text-[0.6875rem] transition-colors duration-[var(--t-fast)] ${
                    days === w.days ? 'bg-brand/12 text-brand' : 'text-ink-muted hover:text-ink'
                  }`}
                >
                  {w.label}
                </button>
              ))}
            </div>
            <Tooltip label="Recalculate now" side="bottom">
              <button
                onClick={() => load(days, { quiet: true, fresh: true })}
                className="btn-ghost !p-2"
                aria-label="Refresh"
                disabled={refreshing}
              >
                <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
              </button>
            </Tooltip>
          </>
        }
      />

      {error && (
        <div className="mb-5">
          <InlineError onRetry={() => load(days, { fresh: true })}>{error}</InlineError>
        </div>
      )}

      {loading && !data ? (
        <LoadingPanels />
      ) : !hasAnything && !error ? (
        <div className="card">
          <EmptyState
            icon={BarChart3}
            title="Nothing to report yet"
            description="These panels fill in as claims are checked. Run one and the volume, sources and latency figures start here."
            action={<a href="/analyze" className="btn-primary !px-4 !py-2 text-sm">Check a claim</a>}
          />
        </div>
      ) : (
        <div className="space-y-5">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              icon={BarChart3}
              label="Analysed"
              value={analysed.toLocaleString()}
              note={`in ${days} days`}
              trend={volumeTrend}
              goodDirection="up"
              spark={spark}
            />
            <StatCard
              icon={Gauge}
              label="Abstained"
              value={percent(abstention)}
              note={confidence?.total ? `${confidence.abstentions} of ${confidence.total}` : 'no analyses'}
              tone={abstentionTone}
            />
            <StatCard
              icon={Timer}
              label="Median time"
              value={seconds(latency?.p50)}
              note={latency?.count ? `p95 ${seconds(latency.p95)}` : 'no samples'}
            />
            <StatCard
              icon={Activity}
              label="Reader agreement"
              value={calibration?.reliable_sample ? percent(calibration.agreement_rate) : '—'}
              note={
                calibration?.feedback_count
                  ? `${calibration.feedback_count} response${calibration.feedback_count === 1 ? '' : 's'}`
                  : 'no feedback yet'
              }
            />
          </div>

          <Section
            title="Volume by verdict"
            description="Daily counts. Quiet days are drawn as zero rather than skipped, so the chart never interpolates across a gap."
          >
            <VolumeChart data={volume} />
          </Section>

          <div className="grid gap-5 xl:grid-cols-[1.4fr_1fr]">
            <Section
              title="Sources relied on"
              description="Bar length is citations; the split within it is how that domain's evidence fell. Credibility is a mean, shown only where there are enough citations to mean something."
            >
              <SourceBars sources={data?.sources?.sources ?? []} />
            </Section>

            <Section
              title="Where readers disagreed"
              description="Self-selected feedback — people who disagree are likelier to leave it. Read it as a prompt to investigate, not as an accuracy score."
            >
              {calibration?.by_verdict?.length ? (
                <ul className="space-y-1">
                  {calibration.by_verdict.map((row) => (
                    <li
                      key={row.verdict}
                      className="flex items-center justify-between gap-3 rounded-lg px-2 py-2 transition-colors duration-[var(--t-fast)] hover:bg-[rgb(var(--c-surface-hover)/var(--hover-alpha))]"
                    >
                      <div className="min-w-0">
                        <div className="truncate text-[0.8125rem] text-ink-secondary">{row.verdict}</div>
                        <div className="text-[0.6875rem] text-ink-muted">
                          {row.agreed} agreed · {row.disagreed} disagreed
                        </div>
                      </div>
                      <span
                        className="shrink-0 font-mono text-sm tnum text-ink"
                        title={row.reliable_sample ? undefined : 'Too few responses to compute a meaningful rate'}
                      >
                        {row.reliable_sample ? percent(row.agreement_rate) : '—'}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState
                  icon={Activity}
                  title="No feedback yet"
                  description="Reader agreement appears once people start rating verdicts."
                  className="!py-8"
                />
              )}
            </Section>
          </div>

          <p className="pb-2 text-[0.6875rem] leading-relaxed text-ink-muted">
            Figures cover the trailing {days} days and exclude analyses that failed.
            Rates are shown as unavailable rather than rounded where the sample is
            too small to support one.
            {data?.computed_at && <> Computed {staleness(data.computed_at)}; refresh recalculates.</>}
          </p>
        </div>
      )}
    </div>
  );
}
