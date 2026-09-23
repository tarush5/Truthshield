import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Clock, CornerDownLeft, Moon, Search, ShieldQuestion, Sun,
} from 'lucide-react';

import { api } from '../lib/api';
import { getVerdict } from '../lib/verdict';

/**
 * ⌘K palette.
 *
 * Navigation plus a search over past analyses, which is the thing that
 * actually needs one — the history list grows without bound and scrolling it
 * to find a claim from last week is the slow path.
 *
 * Reports load once on first open and are filtered client-side. The whole
 * list is a few hundred bytes per row, and a request per keystroke would be
 * worse for both latency and the rate limiter.
 */
export default function CommandPalette({ open, onClose, onToggleTheme, theme }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [reports, setReports] = useState(null);
  const [active, setActive] = useState(0);
  const inputRef = useRef(null);
  const listRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    setQuery('');
    setActive(0);
    // Focus after paint, or the element is not yet in the document.
    requestAnimationFrame(() => inputRef.current?.focus());
  }, [open]);

  useEffect(() => {
    if (!open || reports !== null) return;
    let alive = true;
    api.reports(50)
      .then((data) => alive && setReports(data))
      .catch(() => alive && setReports([]));
    return () => { alive = false; };
  }, [open, reports]);

  const items = useMemo(() => {
    const q = query.trim().toLowerCase();

    const actions = [
      {
        id: 'analyze',
        icon: ShieldQuestion,
        label: 'Check a claim',
        hint: 'New analysis',
        run: () => navigate('/analyze'),
      },
      {
        id: 'history',
        icon: Clock,
        label: 'History',
        hint: 'Past analyses',
        run: () => navigate('/history'),
      },
      {
        id: 'theme',
        icon: theme === 'dark' ? Sun : Moon,
        label: `Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`,
        run: onToggleTheme,
      },
    ].filter((a) => !q || a.label.toLowerCase().includes(q));

    const matches = (reports ?? [])
      .filter((r) => !q || (r.excerpt || '').toLowerCase().includes(q))
      .slice(0, 7)
      .map((r) => {
        const meta = getVerdict(r.verdict);
        return {
          id: `report-${r.id}`,
          icon: meta.icon,
          label: r.excerpt || 'Media submission',
          hint: meta.headline,
          tone: meta.tone,
          run: () => navigate(`/report/${r.id}`),
        };
      });

    return [...actions, ...matches];
  }, [query, reports, navigate, onToggleTheme, theme]);

  // Clamp when the result count shrinks under the cursor.
  useEffect(() => {
    setActive((i) => Math.min(i, Math.max(items.length - 1, 0)));
  }, [items.length]);

  const choose = useCallback((item) => {
    if (!item) return;
    onClose();
    item.run();
  }, [onClose]);

  const onKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActive((i) => (i + 1) % Math.max(items.length, 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive((i) => (i - 1 + items.length) % Math.max(items.length, 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      choose(items[active]);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
    }
  };

  // Keep the highlighted row in view when arrowing past the fold.
  useEffect(() => {
    listRef.current?.querySelector('[data-active="true"]')
      ?.scrollIntoView({ block: 'nearest' });
  }, [active]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center bg-black/55 px-4 pt-[12vh] backdrop-blur-sm"
      onMouseDown={onClose}
      role="presentation"
    >
      <div
        className="rise w-full max-w-xl overflow-hidden rounded-2xl border border-line bg-surface shadow-lg"
        onMouseDown={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
      >
        <div className="flex items-center gap-3 border-b border-line px-4">
          <Search className="h-4 w-4 shrink-0 text-ink-muted" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Search your analyses, or jump somewhere…"
            className="w-full bg-transparent py-3.5 text-sm text-ink outline-none placeholder:text-ink-muted"
            aria-label="Search"
          />
          <kbd className="shrink-0 rounded border border-line px-1.5 py-0.5 font-mono text-[10px] text-ink-muted">
            ESC
          </kbd>
        </div>

        <ul ref={listRef} className="max-h-80 overflow-y-auto p-1.5">
          {items.length === 0 && (
            <li className="px-3 py-6 text-center text-sm text-ink-muted">
              {reports === null ? 'Loading…' : 'Nothing matches that.'}
            </li>
          )}

          {items.map((item, i) => {
            const Icon = item.icon;
            return (
              <li key={item.id}>
                <button
                  data-active={i === active}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => choose(item)}
                  className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors ${
                    i === active ? 'bg-brand/12' : 'hover:bg-line/[0.05]'
                  }`}
                >
                  <Icon className="h-4 w-4 shrink-0 text-ink-muted" />
                  <span className="min-w-0 flex-1 truncate text-sm text-ink">
                    {item.label}
                  </span>
                  {item.hint && (
                    <span className="shrink-0 text-2xs text-ink-muted">{item.hint}</span>
                  )}
                  {i === active && (
                    <CornerDownLeft className="h-3.5 w-3.5 shrink-0 text-ink-muted" />
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
