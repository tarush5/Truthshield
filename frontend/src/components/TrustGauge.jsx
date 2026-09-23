import React, { useEffect, useRef, useState } from 'react';

import { TONE_TEXT_VAR, TONE_VAR, getVerdict, trustBand } from '../lib/verdict';

/**
 * The trust dial — the report's hero figure.
 *
 * A 270° arc rather than a full ring. A closed circle reads as
 * "complete / incomplete", which is not what a 0–100 trust score means; the
 * gap at the bottom gives the sweep a start and an end so it reads as a
 * position on a scale.
 *
 * Band ticks give the reader the scale without a separate legend, and the
 * verdict sits underneath with an icon, so colour never carries the meaning
 * on its own.
 */

const SIZE = 200;
const CENTER = SIZE / 2;
const RADIUS = 80;
const TRACK = 9;
const SWEEP = 270;      // degrees of arc
const START = 135;      // degrees, clockwise from 3 o'clock

// Matches the verdict bands in the scorer, so the number and the label can
// never tell the reader two different stories.
const BAND_EDGES = [25, 45, 65, 85];

const polar = (deg, r = RADIUS) => {
  const rad = (deg * Math.PI) / 180;
  return { x: CENTER + r * Math.cos(rad), y: CENTER + r * Math.sin(rad) };
};

const arc = (from, to, r = RADIUS) => {
  const a = polar(from, r);
  const b = polar(to, r);
  return `M ${a.x} ${a.y} A ${r} ${r} 0 ${Math.abs(to - from) > 180 ? 1 : 0} 1 ${b.x} ${b.y}`;
};

export default function TrustGauge({ score = 50, verdict, confidenceBand, size = SIZE }) {
  const safe = Math.max(0, Math.min(100, Math.round(score ?? 0)));
  const meta = getVerdict(verdict);
  const Icon = meta.icon;

  // Tone follows the verdict when there is one, so the dial and the label
  // always agree; it falls back to the score band for a bare gauge.
  const tone = verdict ? meta.tone : trustBand(safe).tone;
  const mark = `rgb(var(${TONE_VAR[tone]}))`;
  const text = `rgb(var(${TONE_TEXT_VAR[tone]}))`;

  const [shown, setShown] = useState(0);
  const raf = useRef();

  useEffect(() => {
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
      setShown(safe);
      return undefined;
    }
    const duration = 1000;
    const t0 = performance.now();
    const tick = (now) => {
      const p = Math.min((now - t0) / duration, 1);
      setShown(safe * (1 - Math.pow(1 - p, 3)));
      if (p < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [safe]);

  const end = START + (shown / 100) * SWEEP;
  const head = polar(end);

  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          viewBox={`0 0 ${SIZE} ${SIZE}`}
          className="h-full w-full overflow-visible"
          role="img"
          aria-label={`Trust score ${safe} out of 100 — ${meta.headline}`}
        >
          {/* A soft halo in the verdict's colour. Sits under the track so it
              reads as light coming off the arc, not as a second ring. */}
          {shown > 2 && (
            <circle
              cx={CENTER}
              cy={CENTER}
              r={RADIUS}
              fill="none"
              stroke={mark}
              strokeWidth={TRACK * 2.4}
              opacity="0.07"
              style={{ filter: 'blur(9px)' }}
            />
          )}

          <path
            d={arc(START, START + SWEEP)}
            fill="none"
            stroke="rgb(var(--c-border) / 0.11)"
            strokeWidth={TRACK}
            strokeLinecap="round"
          />

          {/* Band ticks: the scale, without a legend box. Drawn in the page
              colour so they read as gaps cut into the track. */}
          {BAND_EDGES.map((edge) => {
            const a = START + (edge / 100) * SWEEP;
            const outer = polar(a, RADIUS + TRACK / 2 + 0.5);
            const inner = polar(a, RADIUS - TRACK / 2 - 0.5);
            return (
              <line
                key={edge}
                x1={inner.x} y1={inner.y} x2={outer.x} y2={outer.y}
                stroke="rgb(var(--c-page))"
                strokeWidth="2.5"
              />
            );
          })}

          {shown > 0.5 && (
            <>
              <path
                d={arc(START, end)}
                fill="none"
                stroke={mark}
                strokeWidth={TRACK}
                strokeLinecap="round"
              />
              {/* Data end, ringed in the surface colour so it stays legible
                  where it overlaps the track. */}
              <circle
                cx={head.x} cy={head.y} r={TRACK / 2 + 2.5}
                fill={mark}
                stroke="rgb(var(--c-surface))"
                strokeWidth="2.5"
              />
            </>
          )}
        </svg>

        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          {/* Proportional figures, not tabular: equal-width digits make a
              large standalone number look loose. */}
          <span
            className="text-[3.5rem] font-extrabold leading-none tracking-tighter"
            style={{ color: text }}
          >
            {Math.round(shown)}
          </span>
          <span className="mt-1 text-2xs font-semibold uppercase tracking-[0.1em] text-ink-muted">
            Trust score
          </span>
        </div>
      </div>

      <div className="-mt-2 flex flex-col items-center gap-2">
        <span
          className="inline-flex items-center gap-2 rounded-xl px-3.5 py-1.5 text-sm font-bold"
          style={{
            color: text,
            background: `rgb(var(${TONE_VAR[tone]}) / 0.13)`,
            boxShadow: `inset 0 0 0 1px rgb(var(${TONE_VAR[tone]}) / 0.3)`,
          }}
        >
          <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
          {meta.headline}
        </span>

        {confidenceBand && (
          <span className="text-2xs text-ink-muted">
            {String(confidenceBand).replace(/_/g, ' ').toLowerCase()} confidence
          </span>
        )}
      </div>
    </div>
  );
}
