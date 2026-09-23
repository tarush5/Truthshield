import React from 'react';
import { BookOpen, ExternalLink } from 'lucide-react';

/**
 * A generated explanation, shown only with its sources attached.
 *
 * The backend has already stripped any citation that does not resolve and
 * discarded the answer outright if none survived, so anything arriving here
 * cites real retrieved text. This component's job is to make that visible:
 * every `[n]` becomes a link to the source it points at, and the sources it
 * used are listed underneath.
 *
 * The framing matters as much as the text. It is labelled as written from
 * the sources and sits *below* the verdict, because it explains a ruling the
 * scoring engine made — it did not make one.
 */

const CITATION = /(\[\d+(?:\s*,\s*\d+)*\])/g;

function hostOf(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

/** Render `[1]` and `[2,3]` as superscript links into the source list. */
function withCitations(text, sources) {
  return text.split(CITATION).map((part, i) => {
    const match = /^\[(\d+(?:\s*,\s*\d+)*)\]$/.exec(part);
    if (!match) return <React.Fragment key={i}>{part}</React.Fragment>;

    const numbers = match[1].split(',').map((n) => parseInt(n.trim(), 10));
    return (
      <sup key={i} className="ml-0.5 font-mono text-[0.625rem]">
        {numbers.map((n, j) => {
          const source = sources[n - 1];
          return (
            <React.Fragment key={n}>
              {j > 0 && <span className="text-ink-muted">,</span>}
              {source ? (
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer nofollow"
                  className="text-brand hover:underline"
                  title={source.title}
                >
                  {n}
                </a>
              ) : (
                <span className="text-ink-muted">{n}</span>
              )}
            </React.Fragment>
          );
        })}
      </sup>
    );
  });
}

export default function GroundedExplanation({ explanation, evidence = [] }) {
  if (!explanation?.text) return null;

  const cited = explanation.cited_sources ?? [];
  const used = cited
    .map((n) => ({ n, source: evidence[n - 1] }))
    .filter((entry) => entry.source);

  return (
    <section className="card p-5">
      <header className="mb-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <BookOpen className="h-3.5 w-3.5 text-ink-muted" />
          <h2 className="text-sm font-semibold text-ink">What the sources say</h2>
        </div>
        <span className="font-mono text-[0.6875rem] text-ink-muted">
          {explanation.model}
        </span>
      </header>

      <p className="text-[0.9375rem] leading-relaxed text-ink-secondary">
        {withCitations(explanation.text, evidence)}
      </p>

      {used.length > 0 && (
        <ul className="mt-4 space-y-1.5 border-t border-line pt-3">
          {used.map(({ n, source }) => (
            <li key={n} className="flex gap-2.5 text-[0.6875rem]">
              <span className="shrink-0 font-mono text-ink-muted">[{n}]</span>
              <a
                href={source.url}
                target="_blank"
                rel="noopener noreferrer nofollow"
                className="group min-w-0 flex-1 text-ink-secondary hover:text-ink"
              >
                <span className="line-clamp-1">{source.title}</span>
                <span className="mt-0.5 flex items-center gap-1 font-mono text-ink-muted">
                  {hostOf(source.url)}
                  <ExternalLink className="h-2.5 w-2.5 opacity-0 transition-opacity group-hover:opacity-100" />
                </span>
              </a>
            </li>
          ))}
        </ul>
      )}

      {/* Stated plainly rather than in a tooltip. A reader deciding whether
          to trust this paragraph needs to know it was generated, and that
          the ruling above it was not. */}
      <p className="mt-3 text-[0.6875rem] leading-relaxed text-ink-muted">
        Written from the sources above, which are quoted to it verbatim.
        Citations are checked against the retrieved text before this is
        shown. The verdict was decided by the scoring engine, not by this
        summary.
      </p>
    </section>
  );
}
