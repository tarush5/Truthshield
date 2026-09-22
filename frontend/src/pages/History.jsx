import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { FileSearch, Loader2 } from 'lucide-react';

import { api } from '../lib/api';
import { TONE_TEXT_VAR, TONE_VAR, getVerdict } from '../lib/verdict';

/** Past analyses for the signed-in account. */
export default function History() {
  const [reports, setReports] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    api.reports(50)
      .then((data) => alive && setReports(data))
      .catch((err) => alive && setError(err));
    return () => { alive = false; };
  }, []);

  if (error) {
    return (
      <Centered>
        <p className="text-sm text-ink-secondary">{error.message}</p>
      </Centered>
    );
  }

  if (!reports) {
    return (
      <Centered>
        <Loader2 className="h-6 w-6 animate-spin text-brand-500" />
      </Centered>
    );
  }

  if (reports.length === 0) {
    return (
      <Centered>
        <FileSearch className="h-10 w-10 text-ink-muted" />
        <div className="space-y-1.5 text-center">
          <h1 className="text-lg font-bold text-ink">Nothing checked yet</h1>
          <p className="text-sm text-ink-secondary">
            Your analyses will show up here.
          </p>
        </div>
        <Link to="/analyze" className="btn-primary">Check a claim</Link>
      </Centered>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-5 px-4 sm:px-6 lg:px-8">
      <header className="space-y-1">
        <h1 className="text-2xl font-extrabold tracking-tight text-ink">History</h1>
        <p className="text-sm text-ink-secondary">
          {reports.length} {reports.length === 1 ? 'analysis' : 'analyses'}
        </p>
      </header>

      <ul className="space-y-2">
        {reports.map((report) => {
          const meta = getVerdict(report.verdict);
          const Icon = meta.icon;
          return (
            <li key={report.id}>
              <Link
                to={`/report/${report.id}`}
                className="card-hover flex items-center gap-4 p-4"
              >
                <span
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl"
                  style={{
                    color: `rgb(var(${TONE_TEXT_VAR[meta.tone]}))`,
                    background: `rgb(var(${TONE_VAR[meta.tone]}) / 0.14)`,
                  }}
                >
                  <Icon className="h-4 w-4" />
                </span>

                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-ink">
                    {report.excerpt || 'Media submission'}
                  </p>
                  <p className="text-2xs text-ink-muted">
                    {meta.headline} · trust {report.trust_score} ·{' '}
                    {new Date(report.created_at).toLocaleDateString()}
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
    </div>
  );
}

function Centered({ children }) {
  return (
    <div className="mx-auto flex min-h-[50vh] max-w-md flex-col items-center justify-center gap-4 px-4">
      {children}
    </div>
  );
}
