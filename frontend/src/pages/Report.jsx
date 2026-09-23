import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  AlertTriangle, ArrowLeft, Check, ChevronDown, Clock, Copy,
  ExternalLink, Info, Loader2,
} from 'lucide-react';

import EvidenceSpectrum from '../components/EvidenceSpectrum';
import TrustGauge from '../components/TrustGauge';
import { api, ApiError } from '../lib/api';
import {
  TONE_TEXT_VAR, TONE_VAR, getDetectorStatus, getStance, getVerdict, hostOf,
} from '../lib/verdict';

/**
 * The analysis report.
 *
 * Structured so the verdict can be interrogated rather than just read: every
 * claim shows the sources behind it and which way each one cut, the four
 * score components are broken out, and anything the system could not check is
 * stated explicitly instead of being silently omitted.
 *
 * The previous version had `lg:col-span-8` inside a three-column grid, so the
 * right-hand column silently wrapped onto its own row at every breakpoint.
 */
export default function Report() {
  const { id } = useParams();
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let alive = true;
    api.report(id)
      .then((data) => alive && setReport(data))
      .catch((err) => alive && setError(err));
    return () => { alive = false; };
  }, [id]);

  const share = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* clipboard blocked — the URL is in the address bar anyway */ }
  };

  if (error) return <ReportError error={error} />;
  if (!report) return <ReportSkeleton />;

  const meta = getVerdict(report.verdict);

  return (
    <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8 space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <Link
          to="/analyze"
          className="btn-ghost -ml-3"
        >
          <ArrowLeft className="h-4 w-4" />
          New analysis
        </Link>

        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 text-2xs text-ink-muted">
            <Clock className="h-3.5 w-3.5" />
            {new Date(report.created_at).toLocaleString()}
            {report.processing_time_seconds > 0 && (
              <> · {report.processing_time_seconds.toFixed(1)}s</>
            )}
          </span>
          <button onClick={share} className="btn-secondary !px-3 !py-1.5 text-2xs">
            {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? 'Copied' : 'Share'}
          </button>
        </div>
      </header>

      {/* ── Verdict ─────────────────────────────────────────── */}
      <section className="card p-6 sm:p-8">
        <div className="flex flex-col items-center gap-8 md:flex-row md:items-start">
          <div className="shrink-0">
            <TrustGauge
              score={report.trust_score}
              verdict={report.verdict}
              confidenceBand={report.confidence_band}
            />
          </div>

          <div className="min-w-0 flex-1 space-y-5 text-center md:text-left">
            <div>
              <p className="section-label mb-1.5">What we found</p>
              <p className="text-base leading-relaxed text-ink-secondary">
                {report.summary || meta.gist}
              </p>
            </div>

            {report.reasons?.length > 0 && (
              <ul className="space-y-1.5">
                {report.reasons.map((reason, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-ink-secondary">
                    <Check
                      className="mt-0.5 h-3.5 w-3.5 shrink-0"
                      style={{ color: `rgb(var(${TONE_TEXT_VAR[meta.tone]}))` }}
                    />
                    <span>{reason}</span>
                  </li>
                ))}
              </ul>
            )}

            <FakeProbability value={report.fake_probability} />
          </div>
        </div>
      </section>

      {/* ── Limitations ─────────────────────────────────────── */}
      {report.limitations?.length > 0 && <Limitations items={report.limitations} />}

      {/* ── Score components ────────────────────────────────── */}
      <Breakdown breakdown={report.breakdown} />

      {/* ── Claims ──────────────────────────────────────────── */}
      {report.claims?.length > 0 && (
        <section className="space-y-3">
          <h2 className="section-title">
            {report.claims.length === 1
              ? 'The claim we checked'
              : `The ${report.claims.length} claims we checked`}
          </h2>
          {report.claims.map((claim, i) => <ClaimCard key={i} claim={claim} />)}
        </section>
      )}

      {/* ── Detectors ───────────────────────────────────────── */}
      <Detectors detectors={report.detectors} />

      {/* ── Submitted content ───────────────────────────────── */}
      {report.original_text && (
        <section className="card p-5 space-y-2">
          <h2 className="section-label">What was submitted</h2>
          {report.source_url && (
            <a
              href={report.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-sm text-brand hover:underline"
            >
              {hostOf(report.source_url)}
              <ExternalLink className="h-3 w-3" />
            </a>
          )}
          <p className="max-h-52 overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed text-ink-secondary">
            {report.original_text}
          </p>
        </section>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────── */

/**
 * Misinformation likelihood.
 *
 * The colour comes from the value, not from the verdict. Taking the verdict's
 * tone painted this bar green on a "likely true" report — a green bar filling
 * to 40% under the words "chance this is misinformation", where higher is
 * worse. On this scale low is good and high is bad, so it gets its own ramp.
 *
 * 50% is the neutral point the backend shrinks an uncertain result toward, so
 * the bands sit either side of it rather than at the midpoint of 0–100.
 */
function riskTone(value) {
  if (value >= 60) return 'critical';
  if (value >= 45) return 'warning';
  return 'good';
}

function FakeProbability({ value }) {
  const tone = riskTone(value);
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-3">
        <span className="section-label">Chance this is misinformation</span>
        <span
          className="text-lg font-bold tnum"
          style={{ color: `rgb(var(${TONE_TEXT_VAR[tone]}))` }}
        >
          {value}%
        </span>
      </div>
      <div
        className="progress-bar"
        role="progressbar"
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Chance this is misinformation"
      >
        <div
          className="progress-fill"
          style={{ width: `${value}%`, background: `rgb(var(${TONE_VAR[tone]}))` }}
        />
      </div>
      {/* 50 is "we could not establish much", not "half likely fake". Saying
          so stops an uncertain result reading as a hedged accusation. */}
      {value >= 45 && value <= 55 && (
        <p className="text-2xs text-ink-muted">
          Near 50% means the evidence did not settle this either way.
        </p>
      )}
    </div>
  );
}

function Limitations({ items }) {
  return (
    <section
      className="card-flat p-4"
      style={{ boxShadow: 'inset 0 0 0 1px rgb(var(--c-warning) / 0.28)' }}
    >
      <div className="flex items-start gap-2.5">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-status-warning-text" />
        <div className="space-y-1.5">
          <h2 className="text-sm font-semibold text-ink">What this analysis could not check</h2>
          <ul className="space-y-1">
            {items.map((item, i) => (
              <li key={i} className="text-sm text-ink-secondary">· {item}</li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

const COMPONENT_LABELS = {
  fact_match: 'Fact match',
  source_credibility: 'Source credibility',
  evidence_strength: 'Evidence strength',
  manipulation_risk: 'Manipulation risk',
};

const COMPONENT_HELP = {
  fact_match: 'How the checked claims came out',
  source_credibility: 'How trustworthy the sources that took a side are',
  evidence_strength: 'How much evidence actually took a position',
  manipulation_risk: 'Signs the media itself was altered. 50% means not assessed.',
};

function Breakdown({ breakdown }) {
  if (!breakdown) return null;
  const entries = Object.entries(breakdown);

  return (
    <section className="card p-5 space-y-4">
      <h2 className="section-title">How the score breaks down</h2>
      <div className="space-y-3.5">
        {entries.map(([key, value]) => (
          <div key={key} className="space-y-1.5">
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-sm font-medium text-ink">
                {COMPONENT_LABELS[key] || key}
              </span>
              <span className="tabular-nums text-sm text-ink-secondary">
                {Math.round(value)}%
              </span>
            </div>
            <div className="progress-bar">
              {/* One series, one colour: the axis already names each row, so
                  a different hue per bar would be decoration. */}
              <div
                className="progress-fill"
                style={{ width: `${value}%`, background: 'rgb(var(--c-series-1))' }}
              />
            </div>
            <p className="text-2xs text-ink-muted">{COMPONENT_HELP[key]}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function ClaimCard({ claim }) {
  const [open, setOpen] = useState(false);
  const meta = getVerdict(claim.verdict);
  const Icon = meta.icon;
  const hasEvidence = claim.evidence?.length > 0;

  return (
    <article className="card overflow-hidden">
      <div className="space-y-3 p-5">
        <div className="flex items-start gap-3">
          <span
            className="mt-0.5 inline-flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1 text-2xs font-bold uppercase tracking-wide"
            style={{
              color: `rgb(var(${TONE_TEXT_VAR[meta.tone]}))`,
              background: `rgb(var(${TONE_VAR[meta.tone]}) / 0.14)`,
              boxShadow: `inset 0 0 0 1px rgb(var(${TONE_VAR[meta.tone]}) / 0.32)`,
            }}
          >
            <Icon className="h-3.5 w-3.5" />
            {meta.headline}
          </span>
          <p className="min-w-0 flex-1 text-sm font-medium leading-relaxed text-ink">
            {claim.text}
          </p>
        </div>

        {claim.reasoning && (
          <p className="text-sm leading-relaxed text-ink-secondary">{claim.reasoning}</p>
        )}

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-2xs text-ink-muted">
          <span>Confidence {Math.round(claim.confidence * 100)}%</span>
          {claim.supporting_count > 0 && (
            <span className="text-status-good-text">
              {claim.supporting_count} supporting
            </span>
          )}
          {claim.refuting_count > 0 && (
            <span className="text-status-critical-text">
              {claim.refuting_count} contradicting
            </span>
          )}
        </div>
      </div>

      {hasEvidence && (
        <>
          <div className="border-t border-line">
            <EvidenceSpectrum evidence={claim.evidence} />
          </div>
          <button
            onClick={() => setOpen(!open)}
            className="flex w-full items-center justify-between border-t border-line px-5 py-2.5 text-2xs font-semibold uppercase tracking-wide text-ink-muted transition-colors hover:text-ink"
            aria-expanded={open}
          >
            {open ? 'Hide' : 'Show'} {claim.evidence.length} source
            {claim.evidence.length !== 1 ? 's' : ''}
            <ChevronDown
              className={`h-4 w-4 transition-transform ${open ? 'rotate-180' : ''}`}
            />
          </button>
          {open && (
            <ul className="divide-y divide-line border-t border-line">
              {claim.evidence.map((item, i) => <EvidenceRow key={i} item={item} />)}
            </ul>
          )}
        </>
      )}
    </article>
  );
}

function EvidenceRow({ item }) {
  const stance = getStance(item.stance);
  const StanceIcon = stance.icon;

  return (
    <li className="space-y-1.5 px-5 py-3">
      <div className="flex items-start justify-between gap-3">
        <a
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          className="min-w-0 flex-1 text-sm font-medium text-ink hover:text-brand"
        >
          {item.title}
        </a>
        <span
          className="inline-flex shrink-0 items-center gap-1 rounded-md px-1.5 py-0.5 text-2xs font-semibold"
          style={{
            color: `rgb(var(${TONE_TEXT_VAR[stance.tone]}))`,
            background: `rgb(var(${TONE_VAR[stance.tone]}) / 0.12)`,
          }}
        >
          <StanceIcon className="h-3 w-3" />
          {stance.label}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-2xs text-ink-muted">
        <span>{hostOf(item.source_domain || item.url)}</span>
        <span>·</span>
        {/* The credibility label comes from the API so the UI and the scorer
            cannot disagree about what a score means. */}
        <span>{item.credibility_label}</span>
      </div>

      {item.snippet && (
        <p className="line-clamp-2 text-2xs leading-relaxed text-ink-muted">{item.snippet}</p>
      )}
    </li>
  );
}

function Detectors({ detectors }) {
  if (!detectors?.length) return null;
  // A check that never applied is noise; one that failed is worth showing.
  const shown = detectors.filter((d) => d.status !== 'not_applicable');
  if (!shown.length) return null;

  return (
    <section className="card p-5 space-y-3">
      <h2 className="section-title">Media checks</h2>
      <ul className="space-y-2.5">
        {shown.map((d) => {
          const status = getDetectorStatus(d.status);
          return (
            <li key={d.name} className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-medium capitalize text-ink">
                  {d.name.replace(/_/g, ' ')}
                </p>
                {d.detail && (
                  <p className="text-2xs leading-relaxed text-ink-muted">{d.detail}</p>
                )}
              </div>
              <span
                className="shrink-0 rounded-md px-2 py-0.5 text-2xs font-semibold"
                style={{
                  color: `rgb(var(${TONE_TEXT_VAR[status.tone]}))`,
                  background: `rgb(var(${TONE_VAR[status.tone]}) / 0.12)`,
                }}
              >
                {status.label}
                {d.counted_toward_score && ` · ${Math.round(d.score * 100)}%`}
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function ReportSkeleton() {
  return (
    <div className="mx-auto max-w-5xl space-y-6 px-4 sm:px-6 lg:px-8">
      <div className="skeleton h-8 w-40" />
      <div className="card p-8">
        <div className="flex flex-col items-center gap-8 md:flex-row md:items-start">
          <div className="skeleton h-48 w-48 shrink-0 rounded-full" />
          <div className="w-full space-y-3">
            <div className="skeleton h-4 w-24" />
            <div className="skeleton h-4 w-full" />
            <div className="skeleton h-4 w-4/5" />
            <div className="skeleton h-4 w-2/3" />
          </div>
        </div>
      </div>
      <div className="skeleton h-40 w-full rounded-2xl" />
    </div>
  );
}

function ReportError({ error }) {
  const notFound = error instanceof ApiError && error.status === 404;
  return (
    <div className="mx-auto max-w-md space-y-5 px-4 py-20 text-center">
      <AlertTriangle className="mx-auto h-10 w-10 text-status-warning-text" />
      <div className="space-y-2">
        <h1 className="text-lg font-bold text-ink">
          {notFound ? 'Report not available' : 'Could not load this report'}
        </h1>
        <p className="text-sm text-ink-secondary">
          {notFound
            ? 'It may have been deleted, or it belongs to another account.'
            : error.message}
        </p>
      </div>
      <Link to="/analyze" className="btn-primary inline-flex">
        <ArrowLeft className="h-4 w-4" />
        Analyze something
      </Link>
    </div>
  );
}
