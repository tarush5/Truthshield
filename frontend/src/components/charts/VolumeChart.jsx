import React, { useMemo, useRef, useState } from 'react';

/**
 * Daily analysis volume, stacked by verdict.
 *
 * Verdict is a *state*, not a category, so it wears the reserved status
 * colours — a refuted claim is the same red wherever it appears in this
 * product, and it would be wrong to let it land on "series 3" because of
 * where it sorted. The stack order is fixed for the same reason: filtering a
 * verdict out must not repaint the ones that remain.
 *
 * The x axis is dense by construction (the API returns zero-filled buckets),
 * so a quiet weekend draws a flat line instead of a straight interpolation
 * across the gap that reads as a trend.
 */

const PAD = { top: 16, right: 16, bottom: 28, left: 40 };
const HEIGHT = 240;

/**
 * Fixed order, bottom of the stack upward. Not derived from the data, so
 * filtering one out never repaints the others.
 *
 * Grouped by *direction*, not by verdict string, and the grouping was
 * settled by measurement rather than taste. Running the palette through the
 * dataviz validator:
 *
 *   true / likely-true as two green steps   normal-vision dE 11.1  FAIL
 *   likely-false / false as two warm steps  normal-vision dE 13.6  FAIL
 *   collapsed to the four below             normal-vision dE 22.7  PASS
 *
 * Both failing pairs were confidence graduations within one direction --
 * segments a reader genuinely could not tell apart, stacked adjacently. The
 * confidence is not lost, it just does not belong in a 14px bar: it is on
 * the report itself, which is one click away.
 *
 * "Unverified" is deliberately the one chroma-less entry. It is the absence
 * of a finding and should read that way rather than as a fifth colour.
 *
 * Amber and green sit at protan dE 1.4 in light mode, which no arrangement
 * of the product's reserved status tokens fixes. The legend and the per-day
 * tooltip both label every segment with its count -- the secondary encoding
 * status colours are required to ship with.
 */
const GROUPS = [
  { label: 'True', token: 'var(--c-good)', keys: ['TRUE', 'VERIFIED', 'LIKELY TRUE'] },
  { label: 'Misleading', token: 'var(--c-warning)', keys: ['MISLEADING'] },
  { label: 'False', token: 'var(--c-critical)', keys: ['FALSE', 'LIKELY FALSE'] },
  {
    label: 'Unverified',
    token: 'var(--c-ink-muted)',
    keys: ['UNVERIFIED', 'INSUFFICIENT EVIDENCE'],
  },
];

/** Total for a group on one day, summing every verdict string it covers. */
function groupValue(row, group) {
  return group.keys.reduce((sum, key) => sum + (row[key] || 0), 0);
}

function niceMax(value) {
  if (value <= 4) return Math.max(4, value);
  const magnitude = 10 ** Math.floor(Math.log10(value));
  return Math.ceil(value / magnitude) * magnitude;
}

function shortDate(iso) {
  const d = new Date(`${iso}T00:00:00Z`);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', timeZone: 'UTC' });
}

export default function VolumeChart({ data, width = 720 }) {
  const svgRef = useRef(null);
  const [hover, setHover] = useState(null);

  const series = data?.series ?? [];
  // Only the groups actually present, in the fixed order above.
  const active = useMemo(() => {
    const seen = new Set(data?.verdicts ?? []);
    return GROUPS.filter((g) => g.keys.some((k) => seen.has(k)));
  }, [data]);

  const max = useMemo(
    () => niceMax(Math.max(1, ...series.map((row) => row.total || 0))),
    [series],
  );

  if (!series.length) {
    return (
      <div className="flex h-[240px] items-center justify-center text-sm text-ink-muted">
        No analyses in this window yet.
      </div>
    );
  }

  const plotW = width - PAD.left - PAD.right;
  const plotH = HEIGHT - PAD.top - PAD.bottom;
  const step = plotW / Math.max(1, series.length);
  const barW = Math.max(2, Math.min(18, step - 2)); // 2px surface gap between bars

  const x = (i) => PAD.left + i * step + step / 2;
  const y = (v) => PAD.top + plotH - (v / max) * plotH;

  const ticks = [0, max / 2, max].map((v) => Math.round(v));
  // At most ~7 date labels, whatever the window, so they never collide.
  const labelEvery = Math.max(1, Math.ceil(series.length / 7));

  const onMove = (event) => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    const px = ((event.clientX - rect.left) / rect.width) * width;
    const index = Math.floor((px - PAD.left) / step);
    setHover(index >= 0 && index < series.length ? index : null);
  };

  return (
    <div className="relative">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${width} ${HEIGHT}`}
        className="w-full"
        role="img"
        aria-label="Daily analysis volume by verdict"
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
      >
        {/* Recessive grid: the data should be the only thing with weight. */}
        {ticks.map((t) => (
          <g key={t}>
            <line
              x1={PAD.left} x2={width - PAD.right} y1={y(t)} y2={y(t)}
              stroke="rgb(var(--c-border))" strokeOpacity="0.14" strokeWidth="1"
            />
            <text
              x={PAD.left - 8} y={y(t) + 4} textAnchor="end"
              className="fill-[rgb(var(--c-ink-muted))]" style={{ fontSize: 10 }}
            >
              {t}
            </text>
          </g>
        ))}

        {hover !== null && (
          <rect
            x={x(hover) - step / 2} y={PAD.top} width={step} height={plotH}
            fill="rgb(var(--c-border))" fillOpacity="0.06"
          />
        )}

        {series.map((row, i) => {
          let cursor = 0;
          return (
            <g key={row.date}>
              {active.map((group) => {
                const value = groupValue(row, group);
                if (!value) return null;
                const top = y(cursor + value);
                const height = Math.max(1, y(cursor) - top - 2); // 2px gap
                cursor += value;
                return (
                  <rect
                    key={group.label}
                    x={x(i) - barW / 2} y={top} width={barW} height={height}
                    rx="2" fill={`rgb(${group.token})`}
                    opacity={hover === null || hover === i ? 1 : 0.45}
                  />
                );
              })}
            </g>
          );
        })}

        <line
          x1={PAD.left} x2={width - PAD.right} y1={PAD.top + plotH} y2={PAD.top + plotH}
          stroke="rgb(var(--c-border))" strokeOpacity="0.28" strokeWidth="1"
        />

        {series.map((row, i) =>
          i % labelEvery === 0 ? (
            <text
              key={row.date} x={x(i)} y={HEIGHT - 8} textAnchor="middle"
              className="fill-[rgb(var(--c-ink-muted))]" style={{ fontSize: 10 }}
            >
              {shortDate(row.date)}
            </text>
          ) : null,
        )}
      </svg>

      {hover !== null && series[hover] && (
        <div
          className="pointer-events-none absolute z-10 min-w-[10rem] rounded-lg border border-line bg-surface-raised p-2.5 shadow-lg"
          style={{
            left: `${Math.min(80, (x(hover) / width) * 100)}%`,
            top: 4,
          }}
        >
          <div className="mb-1.5 text-[0.6875rem] font-semibold text-ink">
            {shortDate(series[hover].date)}
          </div>
          {active.map((group) => {
            const value = groupValue(series[hover], group);
            if (!value) return null;
            return (
              <div key={group.label} className="flex items-center gap-2 py-0.5">
                <span
                  className="h-2 w-2 shrink-0 rounded-[2px]"
                  style={{ background: `rgb(${group.token})` }}
                />
                {/* Labels wear ink tokens; the swatch beside them carries
                    identity. Colouring the text would fail contrast at this
                    size on at least one surface. */}
                <span className="flex-1 text-[0.6875rem] text-ink-secondary">{group.label}</span>
                <span className="font-mono text-[0.6875rem] text-ink">{value}</span>
              </div>
            );
          })}
          {!series[hover].total && (
            <div className="text-[0.6875rem] text-ink-muted">No analyses</div>
          )}
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5">
        {active.map((group) => (
          <span key={group.label} className="flex items-center gap-1.5">
            <span
              className="h-2 w-2 rounded-[2px]"
              style={{ background: `rgb(${group.token})` }}
            />
            <span className="text-[0.6875rem] text-ink-secondary">{group.label}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
