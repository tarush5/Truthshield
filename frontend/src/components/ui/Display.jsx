import React, { useId } from 'react';
import { ArrowDownRight, ArrowRight, ArrowUpRight, Minus } from 'lucide-react';

/**
 * Presentational primitives: Sparkline, StatCard, Tabs, PageHeader, Section.
 *
 * These carry the product's information design rather than just its styling,
 * which is why the rules live in the components instead of in each page: a
 * trend is only ever green when up is actually good, a metric always shows
 * what it was computed from, and a tab list is always a real tab list to a
 * screen reader.
 */

/* ── Sparkline ────────────────────────────────────────────── */

/**
 * Shape, not values.
 *
 * No axes and no labels by design -- it sits beside a number that carries
 * the magnitude, and its whole job is the direction of travel. Scaled to
 * its own min/max, which exaggerates small variation; that is the correct
 * trade for "is this rising", and the wrong one for reading a value off it,
 * which is what the full chart is for.
 */
export function Sparkline({ values = [], width = 72, height = 24, tone = '--c-brand' }) {
  const id = useId();
  if (values.length < 2) return null;

  const max = Math.max(...values);
  const min = Math.min(...values);
  const span = max - min || 1;
  const step = width / (values.length - 1);

  const points = values.map((v, i) => [
    i * step,
    height - ((v - min) / span) * (height - 4) - 2,
  ]);
  const line = points.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
  const area = `${line} L${width},${height} L0,${height} Z`;
  const [lastX, lastY] = points[points.length - 1];

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true" className="overflow-visible">
      <defs>
        <linearGradient id={`spark-${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={`rgb(var(${tone}))`} stopOpacity="0.22" />
          <stop offset="100%" stopColor={`rgb(var(${tone}))`} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#spark-${id})`} />
      <path
        d={line}
        fill="none"
        stroke={`rgb(var(${tone}))`}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* The endpoint, so the eye lands on "now" rather than the middle. */}
      <circle cx={lastX} cy={lastY} r="2" fill={`rgb(var(${tone}))`} />
    </svg>
  );
}

/* ── Trend ────────────────────────────────────────────────── */

/**
 * A change, with its direction coloured by whether it is *good*.
 *
 * `goodDirection` exists because up is not always good. Analyses rising is
 * healthy; abstentions rising is not, and painting both green because the
 * arrow points the same way would actively mislead.
 */
export function Trend({ value, goodDirection = 'up', className = '' }) {
  if (value === null || value === undefined || Number.isNaN(value)) return null;

  const flat = Math.abs(value) < 0.5;
  const up = value > 0;
  const good = goodDirection === 'none' ? null : (up === (goodDirection === 'up'));

  const Icon = flat ? Minus : up ? ArrowUpRight : ArrowDownRight;
  const color = flat || good === null
    ? 'text-ink-muted'
    : good
      ? 'text-[rgb(var(--c-good-text))]'
      : 'text-[rgb(var(--c-critical-text))]';

  return (
    <span className={`inline-flex items-center gap-0.5 text-[0.6875rem] font-semibold tnum ${color} ${className}`}>
      <Icon className="h-3 w-3" aria-hidden="true" />
      {flat ? 'flat' : `${Math.abs(value).toFixed(1)}%`}
    </span>
  );
}

/* ── Stat card ────────────────────────────────────────────── */

/**
 * One headline figure.
 *
 * `note` is required by convention rather than by the type system: every
 * rate in this product states what it was computed from, because "100%" at
 * n=1 and at n=400 are different findings and the percentage alone hides
 * which one you have.
 */
export function StatCard({
  icon: Icon,
  label,
  value,
  note,
  trend,
  goodDirection = 'up',
  spark,
  sparkTone,
  tone = 'neutral',
  className = '',
}) {
  const valueTone = {
    neutral: 'text-ink',
    good: 'text-[rgb(var(--c-good-text))]',
    warning: 'text-[rgb(var(--c-warning-text))]',
    critical: 'text-[rgb(var(--c-critical-text))]',
  }[tone];

  return (
    <div className={`card group relative overflow-hidden p-4 transition-colors duration-[var(--t-base)] hover:border-[rgb(var(--c-border)/var(--border-alpha-strong))] ${className}`}>
      <div className="mb-2 flex items-center gap-2">
        {Icon && <Icon className="h-3.5 w-3.5 text-ink-muted" aria-hidden="true" />}
        <span className="section-label !text-ink-muted">{label}</span>
      </div>

      <div className="flex items-end justify-between gap-3">
        <div className="min-w-0">
          <div className={`font-mono text-2xl font-semibold tnum ${valueTone}`}>{value}</div>
          <div className="mt-1 flex items-center gap-2">
            {trend !== undefined && <Trend value={trend} goodDirection={goodDirection} />}
            {note && <span className="truncate text-[0.6875rem] text-ink-muted">{note}</span>}
          </div>
        </div>
        {spark?.length > 1 && (
          <Sparkline values={spark} tone={sparkTone || '--c-brand'} />
        )}
      </div>
    </div>
  );
}

/* ── Tabs ─────────────────────────────────────────────────── */

/**
 * A real tab list.
 *
 * Arrow keys move between tabs and only the active one is tabbable, which
 * is the pattern a screen reader announces as tabs. A row of buttons styled
 * to look like tabs is announced as a row of buttons.
 */
export function Tabs({ tabs, value, onChange, className = '' }) {
  const onKeyDown = (e) => {
    const index = tabs.findIndex((t) => t.value === value);
    if (index < 0) return;

    let next = null;
    if (e.key === 'ArrowRight') next = (index + 1) % tabs.length;
    else if (e.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = tabs.length - 1;

    if (next !== null) {
      e.preventDefault();
      onChange(tabs[next].value);
    }
  };

  return (
    <div
      role="tablist"
      onKeyDown={onKeyDown}
      className={`flex gap-0.5 overflow-x-auto border-b border-line ${className}`}
    >
      {tabs.map((tab) => {
        const selected = tab.value === value;
        return (
          <button
            key={tab.value}
            role="tab"
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(tab.value)}
            className="segment shrink-0 !px-3.5 !py-2.5 !text-[0.8125rem]"
          >
            {tab.icon && <tab.icon className="h-3.5 w-3.5" aria-hidden="true" />}
            {tab.label}
            {tab.count !== undefined && (
              <span className="ml-0.5 rounded-md bg-[rgb(var(--c-border)/0.08)] px-1.5 py-0.5 font-mono text-[0.625rem] text-ink-muted">
                {tab.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/* ── Page furniture ───────────────────────────────────────── */

export function PageHeader({ title, description, actions, eyebrow, className = '' }) {
  return (
    <header className={`mb-7 flex flex-wrap items-end justify-between gap-4 ${className}`}>
      <div className="min-w-0">
        {eyebrow && <div className="eyebrow mb-1.5">{eyebrow}</div>}
        <h1 className="display text-3xl text-ink sm:text-4xl">{title}</h1>
        {description && (
          <p className="mt-2 max-w-prose text-sm leading-relaxed text-ink-muted text-pretty">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </header>
  );
}

export function Section({ title, description, actions, children, className = '' }) {
  return (
    <section className={`card p-5 ${className}`}>
      {(title || actions) && (
        <header className="mb-4 flex items-start justify-between gap-4">
          <div className="min-w-0">
            {title && <h2 className="section-title">{title}</h2>}
            {description && (
              <p className="mt-1 max-w-prose text-[0.6875rem] leading-relaxed text-ink-muted">
                {description}
              </p>
            )}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-1.5">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

/** A link that reads as an onward step rather than as a button. */
export function ArrowLink({ children, ...rest }) {
  return (
    <a
      className="group inline-flex items-center gap-1 text-sm font-semibold text-brand focusable rounded"
      {...rest}
    >
      {children}
      <ArrowRight
        className="h-3.5 w-3.5 transition-transform duration-[var(--t-base)] group-hover:translate-x-0.5"
        aria-hidden="true"
      />
    </a>
  );
}
