import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Eye, ScanLine, Scale } from 'lucide-react';

/**
 * The signed-out entry page.
 *
 * The product's distinguishing claim is that it tells you what it *could not*
 * check, so the page leads with that rather than with a feature list. The
 * sample verdict below the fold is a real response shape — including a
 * limitation — because showing the actual output is more persuasive than
 * describing it.
 */
export default function Landing() {
  return (
    <div className="mx-auto max-w-5xl px-5 sm:px-8">
      {/* ── Hero ─────────────────────────────────────────── */}
      <section className="rise flex flex-col items-center gap-6 py-16 text-center sm:py-24">
        <span className="eyebrow">
          <ScanLine className="h-3.5 w-3.5" />
          Misinformation analysis
        </span>

        <h1 className="display max-w-3xl text-5xl sm:text-6xl lg:text-7xl">
          Find out what's <em>actually</em> true.
        </h1>

        <p className="max-w-prose text-base leading-relaxed text-ink-secondary sm:text-lg">
          Paste a claim and get a verdict with the sources behind it — plus an
          honest list of whatever couldn't be verified. No confident guesses.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
          <Link to="/login" className="btn-primary px-6 py-3 text-base">
            Check a claim
            <ArrowRight className="h-4 w-4" />
          </Link>
          <a href="#how" className="btn-secondary px-6 py-3 text-base">
            How it works
          </a>
        </div>
      </section>

      {/* ── Sample verdict ───────────────────────────────── */}
      <section className="rise rise-1 pb-20">
        <div className="card overflow-hidden">
          <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-3">
            <span className="section-label">A real result</span>
            <span className="badge badge-danger">Likely false</span>
          </div>

          <div className="space-y-5 p-5 sm:p-7">
            <p className="text-lg font-medium leading-snug text-ink">
              "Drinking bleach cures COVID-19 within 24 hours."
            </p>

            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
              <span className="text-ink-secondary">
                <span className="font-semibold text-ink">4 sources</span> contradict this
              </span>
              <span className="text-ink-muted">·</span>
              <span className="text-ink-secondary">
                Trust score <span className="tnum font-semibold text-ink">44</span>/100
              </span>
            </div>

            <ul className="space-y-2 border-t border-line pt-4">
              {[
                ['who.int', 'Authoritative', 'Refutes'],
                ['fullfact.org', 'Authoritative', 'Refutes'],
                ['washingtonpost.com', 'Reliable', 'Refutes'],
              ].map(([host, tier, stance]) => (
                <li key={host} className="flex items-center justify-between gap-3 text-sm">
                  <span className="truncate text-ink-secondary">{host}</span>
                  <span className="flex shrink-0 items-center gap-2">
                    <span className="text-2xs text-ink-muted">{tier}</span>
                    <span className="badge badge-danger">{stance}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* ── How it works ─────────────────────────────────── */}
      <section id="how" className="rise rise-2 scroll-mt-20 pb-24">
        <div className="grid gap-4 sm:grid-cols-3">
          {[
            {
              icon: ScanLine,
              title: 'Pull out the claims',
              body: 'Whatever you submit gets broken into the specific assertions that can actually be checked.',
            },
            {
              icon: Scale,
              title: 'Weigh the sources',
              body: 'Each source is scored on who published it, then read for whether it supports or contradicts the claim.',
            },
            {
              icon: Eye,
              title: 'Say what was missed',
              body: 'Anything that could not run — OCR, deepfake checks, thin evidence — is listed, not hidden.',
            },
          ].map(({ icon: Icon, title, body }) => (
            <div key={title} className="card p-5">
              <span className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-brand/12 text-brand">
                <Icon className="h-4 w-4" />
              </span>
              <h2 className="mb-1.5 text-sm font-semibold text-ink">{title}</h2>
              <p className="text-sm leading-relaxed text-ink-secondary">{body}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
