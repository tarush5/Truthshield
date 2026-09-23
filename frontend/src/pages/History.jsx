import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { FileSearch, Search, X } from 'lucide-react';

import {
  EmptyState, ErrorState, NoResults, PageHeader, Skeleton, Tabs,
} from '../components/ui';
import { api } from '../lib/api';
import { TONE_TEXT_VAR, TONE_VAR, getVerdict } from '../lib/verdict';

/**
 * Past analyses for the signed-in account.
 *
 * The list used to be flat and unsearchable, which is fine at ten entries
 * and useless at two hundred. Filtering happens on the already-fetched
 * page rather than round-tripping: the API returns fifty, so the work is
 * trivial and the results are instant as you type.
 */

const FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'false', label: 'Disputed' },
  { value: 'true', label: 'Held up' },
  { value: 'unresolved', label: 'Unresolved' },
];

/** Which filter bucket a verdict belongs to. */
function bucketOf(verdict) {
  const v = String(verdict || '').toUpperCase();
  if (v.includes('FALSE')) return 'false';
  if (v.includes('TRUE') || v === 'VERIFIED') return 'true';
  return 'unresolved';
}

function relativeDate(iso) {
  const then = new Date(iso);
  const days = Math.floor((Date.now() - then.getTime()) / 86_400_000);
  if (days < 1) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 7) return `${days} days ago`;
  return then.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function LoadingList() {
  return (
    <div className="space-y-2" role="status" aria-busy="true" aria-live="polite">
      <span className="sr-only">Loading history</span>
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="card flex items-center gap-4 p-4">
          <Skeleton className="h-9 w-9 shrink-0 rounded-xl" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3.5 w-3/5" />
            <Skeleton className="h-3 w-2/5" />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function History() {
  const [reports, setReports] = useState(null);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('all');
  const [query, setQuery] = useState('');

  const load = () => {
    setError(null);
    setReports(null);
    api.reports(50).then(setReports).catch(setError);
  };

  useEffect(() => {
    let alive = true;
    api.reports(50)
      .then((data) => alive && setReports(data))
      .catch((err) => alive && setError(err));
    return () => { alive = false; };
  }, []);

  const counts = useMemo(() => {
    const tally = { all: reports?.length ?? 0, false: 0, true: 0, unresolved: 0 };
    reports?.forEach((r) => { tally[bucketOf(r.verdict)] += 1; });
    return tally;
  }, [reports]);

  const visible = useMemo(() => {
    if (!reports) return [];
    const needle = query.trim().toLowerCase();
    return reports.filter((r) => {
      if (filter !== 'all' && bucketOf(r.verdict) !== filter) return false;
      if (!needle) return true;
      return (r.excerpt || '').toLowerCase().includes(needle);
    });
  }, [reports, filter, query]);

  if (error) {
    return (
      <div className="mx-auto w-full max-w-4xl px-5 sm:px-8">
        <PageHeader title="History" />
        <div className="card">
          <ErrorState
            title="Could not load your history"
            description={error.message}
            requestId={error.payload?.request_id}
            onRetry={load}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-4xl px-5 sm:px-8">
      <PageHeader
        eyebrow="Your account"
        title="History"
        description={
          reports
            ? `${reports.length} ${reports.length === 1 ? 'analysis' : 'analyses'}, newest first.`
            : 'Everything you have checked.'
        }
      />

      {reports === null ? (
        <LoadingList />
      ) : reports.length === 0 ? (
        <div className="card">
          <EmptyState
            icon={FileSearch}
            title="Nothing checked yet"
            description="Analyses you run show up here, with the verdict and the sources behind each one."
            action={<Link to="/analyze" className="btn-primary !px-4 !py-2 text-sm">Check a claim</Link>}
          />
        </div>
      ) : (
        <>
          <div className="mb-5 space-y-4">
            <div className="relative">
              <Search
                className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-muted"
                aria-hidden="true"
              />
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Filter by claim text…"
                aria-label="Filter history"
                className="input-field !py-2.5 !pl-10 !pr-10"
              />
              {query && (
                <button
                  onClick={() => setQuery('')}
                  className="focusable absolute right-2.5 top-1/2 -translate-y-1/2 rounded-md p-1 text-ink-muted hover:text-ink"
                  aria-label="Clear filter"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>

            <Tabs
              tabs={FILTERS.map((f) => ({ ...f, count: counts[f.value] }))}
              value={filter}
              onChange={setFilter}
            />
          </div>

          {visible.length === 0 ? (
            <div className="card">
              <NoResults
                query={query}
                onClear={() => { setQuery(''); setFilter('all'); }}
              />
            </div>
          ) : (
            <ul className="space-y-2">
              {visible.map((report) => {
                const meta = getVerdict(report.verdict);
                const Icon = meta.icon;
                return (
                  <li key={report.id}>
                    <Link to={`/report/${report.id}`} className="card-hover flex items-center gap-4 p-4">
                      <span
                        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl"
                        style={{
                          color: `rgb(var(${TONE_TEXT_VAR[meta.tone]}))`,
                          background: `rgb(var(${TONE_VAR[meta.tone]}) / 0.14)`,
                        }}
                      >
                        <Icon className="h-4 w-4" aria-hidden="true" />
                      </span>

                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-ink">
                          {report.excerpt || 'Media submission'}
                        </p>
                        <p className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-[0.6875rem] text-ink-muted">
                          {/* The verdict is named, never colour alone — the
                              tinted icon is a second encoding, not the only one. */}
                          <span className="font-medium">{meta.headline}</span>
                          <span aria-hidden="true">·</span>
                          <span className="tnum">trust {report.trust_score}</span>
                          <span aria-hidden="true">·</span>
                          <span>{relativeDate(report.created_at)}</span>
                        </p>
                      </div>

                      {report.status !== 'complete' && (
                        <span className="badge badge-info shrink-0">{report.status}</span>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
