/**
 * Two small SVG charts for the dashboard.
 *
 * They replace Recharts, which pulled about 100 kB gzipped (Recharts, D3,
 * Redux Toolkit, Immer) into the dashboard for one area chart and one bar
 * chart. Each chart also renders its data as a visually hidden table, so
 * screen-reader users get the numbers rather than a picture.
 */
import { useLayoutEffect, useRef, useState, type PointerEvent, type ReactNode } from 'react';

const M = { top: 10, right: 8, bottom: 22, left: 30 };
const GRID = 'hsl(0 0% 12%)';
const AXIS = 'hsl(0 0% 40%)';

function useSize<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const update = () => setSize({ width: el.clientWidth, height: el.clientHeight });
    update();
    if (typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(update);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return [ref, size] as const;
}

/** Integer ticks from 0 with a 1/2/5 step, at most six of them. */
export function niceTicks(max: number): number[] {
  if (max <= 0) return [0, 1];
  const rough = max / 5;
  const pow = 10 ** Math.floor(Math.log10(rough));
  const step = Math.max(1, [1, 2, 5, 10].map((f) => f * pow).find((s) => s >= rough) ?? pow * 10);
  const ticks: number[] = [];
  for (let v = 0; v <= max + step - 1e-9 && ticks.length < 12; v += step) ticks.push(v);
  return ticks;
}

/** Monotone cubic interpolation (Fritsch–Carlson): smooth, never overshoots below zero. */
function monotonePath(pts: [number, number][]): string {
  const n = pts.length;
  if (n === 0) return '';
  if (n === 1) return `M${pts[0][0]},${pts[0][1]}`;
  const dx: number[] = [];
  const slope: number[] = [];
  for (let i = 0; i < n - 1; i++) {
    dx.push(pts[i + 1][0] - pts[i][0]);
    slope.push((pts[i + 1][1] - pts[i][1]) / (dx[i] || 1));
  }
  const t: number[] = [slope[0]];
  for (let i = 1; i < n - 1; i++) t.push(slope[i - 1] * slope[i] <= 0 ? 0 : (slope[i - 1] + slope[i]) / 2);
  t.push(slope[n - 2]);
  for (let i = 0; i < n - 1; i++) {
    if (slope[i] === 0) {
      t[i] = 0;
      t[i + 1] = 0;
      continue;
    }
    const a = t[i] / slope[i];
    const b = t[i + 1] / slope[i];
    const h = a * a + b * b;
    if (h > 9) {
      const k = 3 / Math.sqrt(h);
      t[i] = k * a * slope[i];
      t[i + 1] = k * b * slope[i];
    }
  }
  let d = `M${pts[0][0]},${pts[0][1]}`;
  for (let i = 0; i < n - 1; i++) {
    const h = dx[i] / 3;
    d += `C${pts[i][0] + h},${pts[i][1] + h * t[i]} ${pts[i + 1][0] - h},${pts[i + 1][1] - h * t[i + 1]} ${pts[i + 1][0]},${pts[i + 1][1]}`;
  }
  return d;
}

function Tooltip({ x, y, width, children }: { x: number; y: number; width: number; children: ReactNode }) {
  // Flip to the left of the cursor in the right half so it never clips.
  const flip = x > width / 2;
  return (
    <div
      className="pointer-events-none absolute z-10 whitespace-nowrap rounded-xl border border-stroke bg-[hsl(0_0%_8%)] px-3 py-2 text-xs shadow-lg"
      style={{ left: x, top: y, transform: `translate(${flip ? 'calc(-100% - 12px)' : '12px'}, -50%)` }}
    >
      {children}
    </div>
  );
}

function YGrid({ ticks, y, width }: { ticks: number[]; y: (v: number) => number; width: number }) {
  return (
    <g>
      {ticks.map((v) => (
        <g key={v}>
          <line x1={M.left} x2={width - M.right} y1={y(v)} y2={y(v)} stroke={GRID} />
          <text x={M.left - 8} y={y(v)} dy="0.32em" textAnchor="end" fontSize={11} fill={AXIS}>
            {v}
          </text>
        </g>
      ))}
    </g>
  );
}

export type Series<T> = { key: keyof T & string; label: string; color: string; fill?: boolean };

export function AreaChart<T extends Record<string, number | string>>({
  data,
  xKey,
  series,
  formatX = String,
  label,
}: {
  data: T[];
  xKey: keyof T & string;
  series: Series<T>[];
  formatX?: (value: string) => string;
  label: string;
}) {
  const [ref, { width, height }] = useSize<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);

  const innerW = Math.max(0, width - M.left - M.right);
  const innerH = Math.max(0, height - M.top - M.bottom);
  const max = Math.max(0, ...data.flatMap((d) => series.map((s) => Number(d[s.key]) || 0)));
  const ticks = niceTicks(max);
  const top = ticks[ticks.length - 1] || 1;
  const x = (i: number) => M.left + (data.length > 1 ? (i / (data.length - 1)) * innerW : innerW / 2);
  const y = (v: number) => M.top + innerH - (v / top) * innerH;
  const every = Math.max(1, Math.ceil(data.length / Math.max(1, Math.floor(innerW / 56))));

  const onMove = (e: PointerEvent<SVGSVGElement>) => {
    if (!data.length) return;
    const box = e.currentTarget.getBoundingClientRect();
    const rel = (e.clientX - box.left - M.left) / (innerW || 1);
    setHover(Math.min(data.length - 1, Math.max(0, Math.round(rel * (data.length - 1)))));
  };

  return (
    <div ref={ref} className="relative h-full w-full">
      {width > 0 && (
        <svg width={width} height={height} aria-hidden onPointerMove={onMove} onPointerLeave={() => setHover(null)} className="touch-pan-y">
          <defs>
            <linearGradient id="area-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#89AACC" stopOpacity={0.45} />
              <stop offset="100%" stopColor="#4E85BF" stopOpacity={0} />
            </linearGradient>
          </defs>
          <YGrid ticks={ticks} y={y} width={width} />
          {data.map((d, i) =>
            i % every === 0 ? (
              <text key={i} x={x(i)} y={height - 6} textAnchor="middle" fontSize={11} fill={AXIS}>
                {formatX(String(d[xKey]))}
              </text>
            ) : null,
          )}
          {series.map((s) => {
            const pts = data.map((d, i) => [x(i), y(Number(d[s.key]) || 0)] as [number, number]);
            const line = monotonePath(pts);
            return (
              <g key={s.key}>
                {s.fill && pts.length > 0 && (
                  <path d={`${line}L${pts[pts.length - 1][0]},${y(0)}L${pts[0][0]},${y(0)}Z`} fill="url(#area-fill)" />
                )}
                <path d={line} fill="none" stroke={s.color} strokeWidth={s.fill ? 2 : 1.5} strokeLinejoin="round" />
              </g>
            );
          })}
          {hover !== null && (
            <g>
              <line x1={x(hover)} x2={x(hover)} y1={M.top} y2={M.top + innerH} stroke={AXIS} strokeDasharray="3 3" />
              {series.map((s) => (
                <circle key={s.key} cx={x(hover)} cy={y(Number(data[hover][s.key]) || 0)} r={3.5} fill={s.color} stroke="hsl(0 0% 4%)" strokeWidth={1.5} />
              ))}
            </g>
          )}
        </svg>
      )}
      {hover !== null && data[hover] && (
        <Tooltip x={x(hover)} y={M.top + innerH / 2} width={width}>
          <p className="mb-1 text-[#aaa]">{String(data[hover][xKey])}</p>
          {series.map((s) => (
            <p key={s.key} style={{ color: s.color }}>
              {s.label}: {String(data[hover][s.key])}
            </p>
          ))}
        </Tooltip>
      )}
      <table className="sr-only">
        <caption>{label}</caption>
        <thead>
          <tr>
            <th scope="col">Date</th>
            {series.map((s) => <th key={s.key} scope="col">{s.label}</th>)}
          </tr>
        </thead>
        <tbody>
          {data.map((d, i) => (
            <tr key={i}>
              <th scope="row">{String(d[xKey])}</th>
              {series.map((s) => <td key={s.key}>{String(d[s.key])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function BarChart({ data, label }: { data: { label: string; value: number; color: string }[]; label: string }) {
  const [ref, { width, height }] = useSize<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);

  const innerW = Math.max(0, width - M.left - M.right);
  const innerH = Math.max(0, height - M.top - M.bottom);
  const ticks = niceTicks(Math.max(0, ...data.map((d) => d.value)));
  const top = ticks[ticks.length - 1] || 1;
  const y = (v: number) => M.top + innerH - (v / top) * innerH;
  const band = data.length ? innerW / data.length : 0;
  const barW = band * 0.6;

  return (
    <div ref={ref} className="relative h-full w-full">
      {width > 0 && (
        <svg width={width} height={height} aria-hidden onPointerLeave={() => setHover(null)}>
          <YGrid ticks={ticks} y={y} width={width} />
          {data.map((d, i) => {
            const bx = M.left + band * i + (band - barW) / 2;
            const by = y(d.value);
            const h = M.top + innerH - by;
            const r = Math.min(8, barW / 2, h);
            return (
              <g key={d.label} onPointerEnter={() => setHover(i)}>
                <rect x={M.left + band * i} y={M.top} width={band} height={innerH} fill={hover === i ? 'hsl(0 0% 12% / 0.5)' : 'transparent'} />
                {h > 0 && (
                  <path
                    d={`M${bx},${by + h}V${by + r}Q${bx},${by} ${bx + r},${by}H${bx + barW - r}Q${bx + barW},${by} ${bx + barW},${by + r}V${by + h}Z`}
                    fill={d.color}
                  />
                )}
                <text x={bx + barW / 2} y={height - 6} textAnchor="middle" fontSize={11} fill={AXIS}>
                  {d.label}
                </text>
              </g>
            );
          })}
        </svg>
      )}
      {hover !== null && data[hover] && (
        <Tooltip x={M.left + band * hover + band / 2} y={y(data[hover].value) - 8} width={width}>
          <p className="text-[#aaa]">{data[hover].label}</p>
          <p style={{ color: data[hover].color }}>count: {data[hover].value}</p>
        </Tooltip>
      )}
      <table className="sr-only">
        <caption>{label}</caption>
        <tbody>
          {data.map((d) => (
            <tr key={d.label}>
              <th scope="row">{d.label}</th>
              <td>{d.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
