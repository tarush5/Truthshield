import React from 'react';
import { AlertTriangle, Inbox, RefreshCw, SearchX } from 'lucide-react';

/**
 * The three states every data surface needs and most products forget:
 * loading, empty, and broken.
 *
 * They live together because they are one decision, not three. A panel is in
 * exactly one of these states or it has data, and keeping them in one file
 * makes it obvious when a page has handled two of the three.
 */

/* ── Loading ──────────────────────────────────────────────────
   Skeletons rather than a spinner. A spinner says "wait" and nothing else;
   a skeleton says how much is coming and where it will be, so the layout
   does not jump when it arrives. */

export function Skeleton({ className = '', ...rest }) {
  return <div className={`skeleton ${className}`} aria-hidden="true" {...rest} />;
}

export function SkeletonText({ lines = 3, className = '' }) {
  return (
    <div className={`space-y-2 ${className}`} aria-hidden="true">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className="h-3"
          // The last line short, like real text. A block of equal-length
          // bars reads as a table, and the eye expects a paragraph.
          style={{ width: i === lines - 1 ? '62%' : '100%' }}
        />
      ))}
    </div>
  );
}

export function SkeletonCard({ className = '' }) {
  return (
    <div className={`card p-5 ${className}`}>
      <Skeleton className="mb-3 h-3 w-24" />
      <Skeleton className="mb-4 h-7 w-32" />
      <SkeletonText lines={2} />
    </div>
  );
}

/**
 * A loading region that announces itself.
 *
 * `aria-busy` and the visually-hidden label are what make this work for a
 * screen reader, which cannot see a shimmer.
 */
export function Loading({ label = 'Loading', children, className = '' }) {
  return (
    <div className={className} role="status" aria-busy="true" aria-live="polite">
      <span className="sr-only">{label}</span>
      {children}
    </div>
  );
}

/* ── Empty ────────────────────────────────────────────────── */

/**
 * Nothing here yet.
 *
 * Always says why it is empty and what to do about it. "No results" alone
 * leaves the reader unsure whether the product is broken or they simply
 * have not used it, and those need different responses.
 */
export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
  className = '',
}) {
  return (
    <div className={`flex flex-col items-center px-6 py-14 text-center ${className}`}>
      <span className="mb-4 flex h-11 w-11 items-center justify-center rounded-2xl border border-line bg-surface-sunken">
        <Icon className="h-5 w-5 text-ink-muted" aria-hidden="true" />
      </span>
      <h3 className="text-[0.9375rem] font-semibold text-ink">{title}</h3>
      {description && (
        <p className="mt-1.5 max-w-sm text-[0.8125rem] leading-relaxed text-ink-muted text-pretty">
          {description}
        </p>
      )}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

/** Empty because a filter or search excluded everything, not because there is no data. */
export function NoResults({ query, onClear }) {
  return (
    <EmptyState
      icon={SearchX}
      title="Nothing matches that"
      description={
        query
          ? `No results for "${query}". Try fewer words, or a different spelling.`
          : 'Try a different filter.'
      }
      action={
        onClear && (
          <button onClick={onClear} className="btn-secondary !px-4 !py-2 text-sm">
            Clear the filter
          </button>
        )
      }
    />
  );
}

/* ── Error ────────────────────────────────────────────────── */

/**
 * Something failed.
 *
 * Says what was being attempted, offers the retry, and shows the request id
 * when the API returned one -- that id is the only thing that lets support
 * find this exact failure, and it is useless sitting in a log the reader
 * cannot reach.
 */
export function ErrorState({
  title = 'That did not load',
  description,
  requestId,
  onRetry,
  className = '',
}) {
  return (
    <div className={`flex flex-col items-center px-6 py-12 text-center ${className}`} role="alert">
      <span className="mb-4 flex h-11 w-11 items-center justify-center rounded-2xl border border-[rgb(var(--c-critical))]/25 bg-[rgb(var(--c-critical))]/[0.07]">
        <AlertTriangle className="h-5 w-5 text-[rgb(var(--c-critical-text))]" aria-hidden="true" />
      </span>
      <h3 className="text-[0.9375rem] font-semibold text-ink">{title}</h3>
      {description && (
        <p className="mt-1.5 max-w-sm text-[0.8125rem] leading-relaxed text-ink-muted text-pretty">
          {description}
        </p>
      )}
      {onRetry && (
        <button onClick={onRetry} className="btn-secondary mt-5 !px-4 !py-2 text-sm">
          <RefreshCw className="h-3.5 w-3.5" />
          Try again
        </button>
      )}
      {requestId && (
        <p className="mt-4 font-mono text-[0.6875rem] text-ink-muted">
          Reference {requestId}
        </p>
      )}
    </div>
  );
}

/** The same failure, inline, where a full-height state would be too much. */
export function InlineError({ children, onRetry }) {
  if (!children) return null;
  return (
    <div
      role="alert"
      className="flex items-start gap-2.5 rounded-xl border border-[rgb(var(--c-critical))]/25 bg-[rgb(var(--c-critical))]/[0.06] p-3.5"
    >
      <AlertTriangle
        className="mt-0.5 h-4 w-4 shrink-0 text-[rgb(var(--c-critical-text))]"
        aria-hidden="true"
      />
      <p className="flex-1 text-[0.8125rem] leading-relaxed text-ink-secondary">{children}</p>
      {onRetry && (
        <button onClick={onRetry} className="btn-ghost shrink-0 !px-2 !py-1 !text-[0.6875rem]">
          Retry
        </button>
      )}
    </div>
  );
}
