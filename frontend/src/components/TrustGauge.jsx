import React, { useEffect, useRef, useState } from 'react';
import { getVerdict, trustBand, TONE_VAR, TONE_TEXT_VAR } from '../lib/verdict';

/**
 * Trust dial — the report's hero figure.
 *
 * A 270° arc rather than a full ring: a full circle reads as "complete /
 * incomplete", which is not what a 0-100 trust score means. The open gap at the
 * bottom gives the arc a start and an end, so the sweep reads as a position on
 * a scale.
 *
 * The figure itself is the hero number and uses proportional figures, not
 * `tabular-nums` — equal-width digits make a large standalone number look
 * loose. Band ticks give the reader the scale without a separate legend, and
 * the verdict icon + label underneath means the colour never carries the
 * meaning alone.
 */

const SIZE = 200;
const CENTER = SIZE / 2;
const RADIUS = 78;
const TRACK_WIDTH = 10;
const SWEEP = 270;            // degrees of arc
const START = 135;            // degrees, measured clockwise from 3 o'clock

const polar = (angleDeg, r = RADIUS) => {
  const a = (angleDeg * Math.PI) / 180;
  return { x: CENTER + r * Math.cos(a), y: CENTER + r * Math.sin(a) };
};

const arcPath = (fromDeg, toDeg, r = RADIUS) => {
  const a = polar(fromDeg, r);
  const b = polar(toDeg, r);
  const large = Math.abs(toDeg - fromDeg) > 180 ? 1 : 0;
  return `M ${a.x} ${a.y} A ${r} ${r} 0 ${large} 1 ${b.x} ${b.y}`;
};

// Band edges from lib/verdict trustBand(), drawn as ticks on the track.
const BAND_EDGES = [25, 45, 65, 85];

export default function TrustGauge({
  score = 50,
  verdict,
  confidenceBand,
  size = SIZE,
}) {
  const safeScore = Math.max(0, Math.min(100, Math.round(score ?? 0)));
  const band = trustBand(safeScore);
  const meta = getVerdict(verdict);
  const VerdictIcon = meta.icon;

  // Tone follows the verdict when there is one, so the dial and the label can
  // never disagree; it falls back to the score band for a bare gauge.
  const tone = verdict ? meta.tone : band.tone;
  const markColor = `rgb(var(${TONE_VAR[tone]}))`;
  const textColor = `rgb(var(${TONE_TEXT_VAR[tone]}))`;

  const [shown, setShown] = useState(0);
  const raf = useRef();

  useEffect(() => {
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    if (reduce) { setShown(safeScore); return; }

    const duration = 1100;
    const start = performance.now();
    const tick = (now) => {
      const p = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      setShown(safeScore * eased);
      if (p < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [safeScore]);

  const endAngle = START + (shown / 100) * SWEEP;
  const needle = polar(endAngle, RADIUS);

  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          viewBox={`0 0 ${SIZE} ${SIZE}`}
          className="w-full h-full overflow-visible"
          role="img"
          aria-label={`Trust score ${safeScore} out of 100 — ${band.label}`}
        >
          {/* Track */}
          <path
            d={arcPath(START, START + SWEEP)}
            fill="none"
            stroke="rgb(var(--c-border) / 0.12)"
            strokeWidth={TRACK_WIDTH}
            strokeLinecap="round"
          />

          {/* Band ticks — the scale, without a legend box */}
          {BAND_EDGES.map((edge) => {
            const a = START + (edge / 100) * SWEEP;
            const outer = polar(a, RADIUS + TRACK_WIDTH / 2);
            const inner = polar(a, RADIUS - TRACK_WIDTH / 2);
            return (
              <line
                key={edge}
                x1={inner.x} y1={inner.y} x2={outer.x} y2={outer.y}
                stroke="rgb(var(--c-page))"
                strokeWidth="2"
              />
            );
          })}

          {/* Value arc */}
          {shown > 0.5 && (
            <path
              d={arcPath(START, endAngle)}
              fill="none"
              stroke={markColor}
              strokeWidth={TRACK_WIDTH}
              strokeLinecap="round"
            />
          )}

          {/* Data-end marker, ringed in the surface colour so it stays legible
              where it overlaps the track */}
          {shown > 0.5 && (
            <circle
              cx={needle.x} cy={needle.y} r={TRACK_WIDTH / 2 + 2.5}
              fill={markColor}
              stroke="rgb(var(--c-surface))"
              strokeWidth="2.5"
            />
          )}
        </svg>

        {/* Hero figure */}
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <div
            className="text-[3.25rem] leading-none font-extrabold tracking-tight"
            style={{ color: textColor }}
          >
            {Math.round(shown)}
          </div>
          <div className="text-2xs font-semibold uppercase tracking-[0.12em] text-ink-muted mt-1.5">
            Trust score
          </div>
        </div>
      </div>

      {/* Verdict — icon + label, so colour is never the only cue */}
      <div className="flex flex-col items-center gap-2 -mt-3">
        <div
          className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-sm font-bold"
          style={{
            color: textColor,
            background: `rgb(var(${TONE_VAR[tone]}) / 0.13)`,
            boxShadow: `inset 0 0 0 1px rgb(var(${TONE_VAR[tone]}) / 0.32)`,
          }}
        >
          <VerdictIcon className="w-4 h-4 shrink-0" aria-hidden="true" />
          {meta.headline}
        </div>

        {confidenceBand && (
          <div className="text-2xs text-ink-muted">
            {String(confidenceBand).replace('_', ' ').toLowerCase()} confidence
          </div>
        )}
      </div>
    </div>
  );
}
