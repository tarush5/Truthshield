import React, { useEffect, useRef, useState } from 'react';
import { Check, Loader2, ShieldAlert } from 'lucide-react';

/**
 * The product, running, on the landing page.
 *
 * A screenshot would be cheaper and would say less. What distinguishes this
 * tool is the *shape* of what it does -- it pulls a claim apart, weighs
 * sources against it, and then tells you what it could not settle -- and
 * that is a sequence, so the page shows the sequence.
 *
 * The content is a real result from the benchmark fixture, including the
 * awkward part: the fourth source is off-topic and the panel says so. A
 * demo that shows four clean confirmations would be advertising a product
 * that does not exist.
 *
 * It stops when scrolled out of view and respects reduced-motion, because
 * an animation looping forever behind a page is a battery cost paid for
 * nothing.
 */

const STAGES = [
  { label: 'Reading the claim', ms: 700 },
  { label: 'Retrieving sources', ms: 1100 },
  { label: 'Weighing each source', ms: 1000 },
  { label: 'Checking what is missing', ms: 800 },
];

const SOURCES = [
  { host: 'who.int', tier: 'Authoritative', stance: 'refutes' },
  { host: 'fullfact.org', tier: 'Authoritative', stance: 'refutes' },
  { host: 'reuters.com', tier: 'Reliable', stance: 'refutes' },
  { host: 'en.wikipedia.org', tier: 'Mixed', stance: 'off-topic' },
];

const HOLD_MS = 3600;

const STANCE_TONE = {
  refutes: { token: '--c-critical', text: '--c-critical-text' },
  supports: { token: '--c-good', text: '--c-good-text' },
  'off-topic': { token: '--c-ink-muted', text: '--c-ink-muted' },
};

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(
    () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false,
  );
  useEffect(() => {
    const query = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    if (!query) return undefined;
    const onChange = (e) => setReduced(e.matches);
    query.addEventListener('change', onChange);
    return () => query.removeEventListener('change', onChange);
  }, []);
  return reduced;
}

export default function LivePreview() {
  const reduced = usePrefersReducedMotion();
  const containerRef = useRef(null);
  const [visible, setVisible] = useState(true);
  const [step, setStep] = useState(reduced ? STAGES.length : 0);

  // Pause off-screen. Without this the timer keeps running for the whole
  // session on a page the reader scrolled past in two seconds.
  useEffect(() => {
    const node = containerRef.current;
    if (!node || !('IntersectionObserver' in window)) return undefined;

    const observer = new IntersectionObserver(
      ([entry]) => setVisible(entry.isIntersecting),
      { threshold: 0.2 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (reduced || !visible) return undefined;

    const done = step >= STAGES.length;
    const delay = done ? HOLD_MS : STAGES[step].ms;
    const timer = setTimeout(() => setStep(done ? 0 : step + 1), delay);
    return () => clearTimeout(timer);
  }, [step, visible, reduced]);

  const settled = step >= STAGES.length;

  return (
    <div ref={containerRef} className="card overflow-hidden">
      <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span className="relative flex h-1.5 w-1.5">
            <span
              className={`h-1.5 w-1.5 rounded-full ${!settled && !reduced ? 'pulse-dot' : ''}`}
              style={{ background: settled ? 'rgb(var(--c-good))' : 'rgb(var(--c-brand))' }}
            />
          </span>
          <span className="section-label">
            {settled ? 'Verdict' : 'Analysing'}
          </span>
        </div>
        {settled && <span className="badge badge-danger">Likely false</span>}
      </div>

      <div className="p-5 sm:p-6">
        <p className="text-[0.9375rem] font-medium leading-snug text-ink sm:text-base">
          “Drinking bleach cures COVID-19 within 24 hours.”
        </p>

        {/* Stages. Reserved height, so the card does not resize under the
            reader as steps complete and the page below stays still. */}
        <ul className="mt-5 space-y-2" aria-hidden="true">
          {STAGES.map((stage, i) => {
            const complete = i < step || settled;
            const active = i === step && !settled;
            return (
              <li
                key={stage.label}
                className="flex items-center gap-2.5 text-[0.8125rem] transition-opacity duration-[var(--t-slow)]"
                style={{ opacity: complete || active ? 1 : 0.32 }}
              >
                <span className="flex h-4 w-4 shrink-0 items-center justify-center">
                  {complete ? (
                    <Check className="h-3.5 w-3.5 text-[rgb(var(--c-good-text))]" />
                  ) : active ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-brand" />
                  ) : (
                    <span className="h-1 w-1 rounded-full bg-[rgb(var(--c-ink-muted))]" />
                  )}
                </span>
                <span className={complete || active ? 'text-ink-secondary' : 'text-ink-muted'}>
                  {stage.label}
                </span>
              </li>
            );
          })}
        </ul>

        {/* Sources reveal as the weighing step completes. */}
        <div
          className="mt-5 border-t border-line pt-4 transition-opacity duration-[var(--t-slow)]"
          style={{ opacity: step >= 3 || settled ? 1 : 0.25 }}
        >
          <ul className="space-y-1.5">
            {SOURCES.map((source, i) => {
              const tone = STANCE_TONE[source.stance];
              const shown = settled || step >= 3;
              return (
                <li
                  key={source.host}
                  className="flex items-center justify-between gap-3 text-[0.8125rem]"
                  style={{
                    opacity: shown ? 1 : 0,
                    transform: shown ? 'none' : 'translateY(4px)',
                    transition: `opacity var(--t-slow) var(--ease) ${i * 70}ms, transform var(--t-slow) var(--ease) ${i * 70}ms`,
                  }}
                >
                  <span className="flex min-w-0 items-center gap-2">
                    <span
                      className="h-1.5 w-1.5 shrink-0 rounded-full"
                      style={{ background: `rgb(var(${tone.token}))` }}
                    />
                    <span className="truncate font-mono text-[0.6875rem] text-ink-secondary">
                      {source.host}
                    </span>
                  </span>
                  <span className="flex shrink-0 items-center gap-2">
                    <span className="text-[0.6875rem] text-ink-muted">{source.tier}</span>
                    <span
                      className="text-[0.6875rem] font-semibold"
                      style={{ color: `rgb(var(${tone.text}))` }}
                    >
                      {source.stance}
                    </span>
                  </span>
                </li>
              );
            })}
          </ul>
        </div>

        {/* The honest part, and the reason this component exists. */}
        <div
          className="mt-4 flex items-start gap-2.5 rounded-xl border border-line bg-surface-sunken p-3 transition-opacity duration-[var(--t-slow)]"
          style={{ opacity: settled ? 1 : 0 }}
        >
          <ShieldAlert className="mt-px h-3.5 w-3.5 shrink-0 text-[rgb(var(--c-warning-text))]" aria-hidden="true" />
          <p className="text-[0.6875rem] leading-relaxed text-ink-muted">
            One retrieved source did not address the claim and was excluded.
            Image forensics did not run on this submission.
          </p>
        </div>
      </div>
    </div>
  );
}
