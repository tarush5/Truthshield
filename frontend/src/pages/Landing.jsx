import React from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight, Eye, Gauge, Link2, ListChecks, Scale, ScanLine, Share2, Sparkles,
} from 'lucide-react';

import LivePreview from '../components/LivePreview';

/**
 * The signed-out entry page.
 *
 * The product's distinguishing claim is that it tells you what it *could
 * not* check, so the page leads with that rather than with a feature list,
 * and the preview beside the headline is the real output shape -- including
 * an off-topic source and a detector that did not run.
 *
 * Every number stated here is one the system actually measures. There is no
 * "99% accurate" banner, because the honest figure is that on the benchmark
 * fixture it answers nine of twelve and declines the rest, and a product
 * about misinformation cannot open by overstating itself.
 */

const CAPABILITIES = [
  {
    icon: ListChecks,
    title: 'Claims, not vibes',
    body: 'Whatever you submit is broken into the specific assertions that can be checked, and each one is ruled on separately.',
  },
  {
    icon: Scale,
    title: 'Sources weighed, not counted',
    body: 'Each source is scored on who published it, then read for whether it actually supports or contradicts the claim.',
  },
  {
    icon: Eye,
    title: 'Gaps stated outright',
    body: 'Anything that could not run — image forensics, thin evidence, an unreachable page — is listed rather than quietly skipped.',
  },
  {
    icon: Gauge,
    title: 'It declines to guess',
    body: 'When the evidence will not settle a claim, the verdict says so. An abstention is a real answer here, not a failure.',
  },
  {
    icon: Sparkles,
    title: 'Explanations you can check',
    body: 'Written from the retrieved sources with every citation verified against them. An answer whose citations do not resolve is discarded.',
  },
  {
    icon: Share2,
    title: 'Shareable, revocable',
    body: 'Send a result to anyone with a link. Revoking it stops every copy at once, and the public view never names who ran the check.',
  },
];

const STEPS = [
  {
    n: '01',
    title: 'Submit',
    body: 'Paste text, drop a link, or upload an image. Progress streams back as each stage completes rather than after all of them.',
  },
  {
    n: '02',
    title: 'Retrieve and weigh',
    body: 'Sources are pulled from fact-check feeds, reference works and news, then each is scored and read for its stance.',
  },
  {
    n: '03',
    title: 'Read the reasoning',
    body: 'A verdict, the trust score behind it, every source it rests on, and a plain list of what could not be established.',
  },
];

export default function Landing() {
  return (
    <div className="mx-auto max-w-6xl px-5 sm:px-8">
      {/* ── Hero ─────────────────────────────────────────────
          Two columns on a wide screen: the claim on the left, the product
          working on the right. Stacked on a phone, preview first-after-copy
          so the fold still carries the value proposition. */}
      <section className="grid items-center gap-10 py-14 sm:py-20 lg:grid-cols-[1.05fr_1fr] lg:gap-14 lg:py-24">
        <div className="rise">
          <span className="eyebrow mb-5">
            <ScanLine className="h-3.5 w-3.5" aria-hidden="true" />
            Misinformation analysis
          </span>

          <h1 className="display text-balance text-5xl sm:text-6xl lg:text-[4.25rem]">
            Find out what's <em>actually</em> true.
          </h1>

          <p className="mt-5 max-w-prose text-base leading-relaxed text-ink-secondary text-pretty sm:text-lg">
            Paste a claim and get a verdict with the sources behind it — plus an
            honest account of whatever could not be verified. No confident guesses.
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link to="/login" className="btn-primary px-6 py-3 text-base">
              Check a claim
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
            <a href="#how" className="btn-secondary px-6 py-3 text-base">
              How it works
            </a>
          </div>

          <dl className="mt-10 flex flex-wrap gap-x-8 gap-y-4 border-t border-line pt-6">
            {[
              ['9 of 12', 'answered on the benchmark'],
              ['0', 'wrong verdicts on it'],
              ['3', 'declined rather than guessed'],
            ].map(([figure, caption]) => (
              <div key={caption}>
                <dt className="font-mono text-xl font-semibold tnum text-ink">{figure}</dt>
                <dd className="mt-0.5 text-[0.6875rem] text-ink-muted">{caption}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="rise rise-1 lg:pl-4">
          <LivePreview />
        </div>
      </section>

      {/* ── Capabilities ─────────────────────────────────── */}
      <section className="rise rise-2 border-t border-line py-16 sm:py-20">
        <div className="mb-10 max-w-prose">
          <h2 className="display text-3xl sm:text-4xl">Built to be checked.</h2>
          <p className="mt-3 text-base leading-relaxed text-ink-secondary text-pretty">
            A verdict you cannot audit is just an assertion with better
            typography. Everything here is designed to be argued with.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {CAPABILITIES.map(({ icon: Icon, title, body }) => (
            <article
              key={title}
              className="card group p-5 transition-all duration-[var(--t-base)] hover:-translate-y-0.5 hover:border-[rgb(var(--c-border)/var(--border-alpha-strong))]"
            >
              <span className="mb-3.5 flex h-9 w-9 items-center justify-center rounded-xl bg-brand/12 text-brand transition-colors duration-[var(--t-base)] group-hover:bg-brand/20">
                <Icon className="h-4 w-4" aria-hidden="true" />
              </span>
              <h3 className="mb-1.5 text-[0.9375rem] font-semibold text-ink">{title}</h3>
              <p className="text-[0.8125rem] leading-relaxed text-ink-secondary text-pretty">{body}</p>
            </article>
          ))}
        </div>
      </section>

      {/* ── How it works ─────────────────────────────────── */}
      <section id="how" className="rise rise-3 scroll-mt-20 border-t border-line py-16 sm:py-20">
        <div className="mb-10 max-w-prose">
          <h2 className="display text-3xl sm:text-4xl">Three steps, nothing hidden.</h2>
        </div>

        <ol className="grid gap-4 sm:grid-cols-3">
          {STEPS.map(({ n, title, body }) => (
            <li key={n} className="card relative overflow-hidden p-5">
              {/* The step number as a watermark rather than a badge: it
                  orders the list without competing with the heading. */}
              <span
                className="pointer-events-none absolute -right-2 -top-3 font-mono text-6xl font-bold text-[rgb(var(--c-border)/0.07)]"
                aria-hidden="true"
              >
                {n}
              </span>
              <h3 className="mb-1.5 text-[0.9375rem] font-semibold text-ink">{title}</h3>
              <p className="text-[0.8125rem] leading-relaxed text-ink-secondary text-pretty">{body}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* ── Close ────────────────────────────────────────── */}
      <section className="border-t border-line py-16 sm:py-20">
        <div className="card relative overflow-hidden p-8 text-center sm:p-12">
          <div className="page-wash pointer-events-none absolute inset-0" aria-hidden="true" />
          <div className="relative">
            <h2 className="display text-3xl sm:text-4xl">Check something.</h2>
            <p className="mx-auto mt-3 max-w-prose text-base leading-relaxed text-ink-secondary text-pretty">
              A claim you saw this morning, a headline that felt off, a screenshot
              somebody forwarded. It takes a few seconds.
            </p>
            <div className="mt-7 flex flex-wrap items-center justify-center gap-3">
              <Link to="/login" className="btn-primary px-6 py-3 text-base">
                Get started
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
            </div>
            <p className="mt-6 flex items-center justify-center gap-1.5 text-[0.6875rem] text-ink-muted">
              <Link2 className="h-3 w-3" aria-hidden="true" />
              Results are private until you share them
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
