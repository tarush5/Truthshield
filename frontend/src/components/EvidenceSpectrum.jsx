import React, { useMemo, useState } from 'react';

import { hostOf } from '../lib/verdict';

/**
 * Where every source sits on the question.
 *
 * Two encodings, both load-bearing:
 *
 *   x — stance. A diverging axis: refutes on the left, supports on the right,
 *       neutral at a gray centre. Diverging is the right family here because
 *       the data has a meaningful midpoint ("this source takes no side"), and
 *       the two poles genuinely oppose.
 *
 *   y — publisher credibility, 0 at the bottom to 1 at the top.
 *
 * Reading it answers the question a verdict alone cannot: *who* is on each
 * side. A cluster of authoritative sources in the top-left is a strong
 * refutation; the same count clustered bottom-right is a weak endorsement,
 * and the chart makes the difference visible without doing arithmetic.
 *
 * Status colours are used rather than a categorical series because stance is
 * a judgement, not an identity — and every mark carries a label in its
 * tooltip, so colour never has to carry the meaning alone.
 */

const W = 720;
const H = 260;
// Left padding fits the longest credibility label ("Authoritative") at the
// tick font size; at 46 it was clipped to "oritative".
const PAD = { top: 18, right: 20, bottom: 34, left: 78 };
const PLOT_W = W - PAD.left - PAD.right;
const PLOT_H = H - PAD.top - PAD.bottom;

// Stance to horizontal position, −1 … 1.
const STANCE_X = {
  REFUTES: -1,
  SUPPORTS: 1,
  NEUTRAL: 0,
  OFF_TOPIC: 0,
};

const STANCE_TONE = {
  REFUTES: '--c-critical',
  SUPPORTS: '--c-good',
  NEUTRAL: '--c-ink-muted',
  OFF_TOPIC: '--c-ink-muted',
};

const CREDIBILITY_TICKS = [
  { at: 1.0, label: 'Authoritative' },
  { at: 0.7, label: 'Reliable' },
  { at: 0.5, label: 'Unknown' },
  { at: 0.2, label: 'Low' },
];

export default function EvidenceSpectrum({ evidence = [] }) {
  const [hovered, setHovered] = useState(null);

  // Jitter is deterministic, derived from the URL: a random offset would move
  // every dot on each render and make the chart impossible to read.
  const points = useMemo(() => {
    const sided = evidence.filter((e) => e.stance !== 'OFF_TOPIC');
    return sided.map((item, i) => {
      const seed = [...(item.url || String(i))].reduce((a, c) => a + c.charCodeAt(0), 0);
      const jitter = ((seed % 100) / 100 - 0.5) * 0.26;
      const stance = String(item.stance || 'NEUTRAL').toUpperCase();
      const x = (STANCE_X[stance] ?? 0) + jitter;
      return {
        ...item,
        stance,
        cx: PAD.left + ((x + 1) / 2) * PLOT_W,
        cy: PAD.top + (1 - Math.max(0, Math.min(1, item.source_score))) * PLOT_H,
        tone: STANCE_TONE[stance] ?? '--c-ink-muted',
      };
    });
  }, [evidence]);

  if (points.length === 0) {
    return (
      <p className="px-5 py-8 text-center text-sm text-ink-muted">
        No source took a position on this claim.
      </p>
    );
  }

  const counts = points.reduce((acc, p) => {
    acc[p.stance] = (acc[p.stance] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label={
          `Evidence spectrum: ${counts.REFUTES || 0} sources contradict, ` +
          `${counts.SUPPORTS || 0} support, plotted against publisher credibility.`
        }
      >
        {/* Credibility gridlines — recessive, behind everything. */}
        {CREDIBILITY_TICKS.map(({ at, label }) => {
          const y = PAD.top + (1 - at) * PLOT_H;
          return (
            <g key={label}>
              <line
                x1={PAD.left} y1={y} x2={W - PAD.right} y2={y}
                stroke="rgb(var(--c-border) / 0.08)"
                strokeWidth="1"
              />
              <text
                x={PAD.left - 8} y={y + 3}
                textAnchor="end"
                className="fill-ink-muted"
                style={{ fontSize: 9.5, letterSpacing: '0.03em' }}
              >
                {label}
              </text>
            </g>
          );
        })}

        {/* The neutral midpoint. Solid, because it is the axis the poles
            diverge from, not just another gridline. */}
        <line
          x1={PAD.left + PLOT_W / 2} y1={PAD.top - 6}
          x2={PAD.left + PLOT_W / 2} y2={PAD.top + PLOT_H + 6}
          stroke="rgb(var(--c-border) / 0.2)"
          strokeWidth="1"
          strokeDasharray="3 3"
        />

        {/* Pole labels, direct rather than in a legend box. */}
        <text
          x={PAD.left} y={H - 10}
          className="fill-ink-muted"
          style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.08em' }}
        >
          ← CONTRADICTS
        </text>
        <text
          x={W - PAD.right} y={H - 10} textAnchor="end"
          className="fill-ink-muted"
          style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.08em' }}
        >
          SUPPORTS →
        </text>

        {points.map((p, i) => {
          const active = hovered === i;
          return (
            <g
              key={`${p.url}-${i}`}
              onMouseEnter={() => setHovered(i)}
              onMouseLeave={() => setHovered(null)}
              style={{ cursor: 'pointer' }}
            >
              {/* Hit target larger than the mark, so a 7px dot is still easy
                  to hover. */}
              <circle cx={p.cx} cy={p.cy} r="14" fill="transparent" />
              <circle
                cx={p.cx} cy={p.cy}
                r={active ? 9 : 7}
                fill={`rgb(var(${p.tone}))`}
                fillOpacity={active ? 1 : 0.82}
                // A ring in the surface colour keeps overlapping dots
                // distinguishable instead of merging into a blob.
                stroke="rgb(var(--c-surface))"
                strokeWidth="2"
                style={{ transition: 'r 0.12s ease-out' }}
              />
            </g>
          );
        })}
      </svg>

      {hovered !== null && points[hovered] && (
        <Tooltip point={points[hovered]} />
      )}

      {/* Counts as text, so the chart is not the only way to read the split. */}
      <div className="flex flex-wrap items-center justify-center gap-x-5 gap-y-1 pb-1 text-2xs">
        {[
          ['REFUTES', 'contradict', '--c-critical'],
          ['NEUTRAL', 'neutral', '--c-ink-muted'],
          ['SUPPORTS', 'support', '--c-good'],
        ].map(([key, label, tone]) =>
          counts[key] ? (
            <span key={key} className="inline-flex items-center gap-1.5 text-ink-secondary">
              <span
                className="h-2 w-2 rounded-full"
                style={{ background: `rgb(var(${tone}))` }}
              />
              <span className="tnum font-semibold text-ink">{counts[key]}</span>
              {label}
            </span>
          ) : null,
        )}
      </div>
    </div>
  );
}

function Tooltip({ point }) {
  // Flip to the left half once the mark passes the midpoint, so the card
  // never runs off the right edge of the plot.
  const onRight = point.cx > W / 2;
  return (
    <div
      className="pointer-events-none absolute z-10 w-56 rounded-xl border border-line bg-surface p-3 shadow-lg"
      style={{
        left: `${(point.cx / W) * 100}%`,
        top: `${(point.cy / H) * 100}%`,
        transform: `translate(${onRight ? '-105%' : '5%'}, -50%)`,
      }}
    >
      <p className="mb-1 line-clamp-2 text-2xs font-semibold leading-snug text-ink">
        {point.title}
      </p>
      <p className="font-mono text-[10px] text-ink-muted">
        {hostOf(point.source_domain || point.url)}
      </p>
      <div className="mt-1.5 flex items-center justify-between text-[10px]">
        <span style={{ color: `rgb(var(${point.tone}))` }} className="font-semibold uppercase">
          {point.stance.toLowerCase()}
        </span>
        <span className="tnum text-ink-muted">
          {Math.round(point.source_score * 100)}% credible
        </span>
      </div>
    </div>
  );
}
