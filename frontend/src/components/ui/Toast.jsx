import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-react';

/**
 * Transient confirmation.
 *
 * Used for the things that used to happen invisibly -- a link copied, a
 * share revoked, a report deleted -- where the only feedback was that a
 * button had stopped looking busy.
 *
 * Deliberately not used for errors that block the task. A toast disappears,
 * so anything the reader has to act on belongs inline next to the thing
 * that failed. This is for "that worked", not "that did not".
 */

const ToastContext = createContext(null);

const TONES = {
  success: { icon: CheckCircle2, token: '--c-good', text: '--c-good-text' },
  error: { icon: XCircle, token: '--c-critical', text: '--c-critical-text' },
  warning: { icon: AlertTriangle, token: '--c-warning', text: '--c-warning-text' },
  info: { icon: Info, token: '--c-brand', text: '--c-brand' },
};

const DEFAULT_DURATION = 4000;

// More than a few stacked and the newest is off-screen on a phone.
const MAX_VISIBLE = 3;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const timers = useRef(new Map());

  const dismiss = useCallback((id) => {
    setToasts((current) => current.filter((t) => t.id !== id));
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const push = useCallback((message, { tone = 'success', duration = DEFAULT_DURATION } = {}) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((current) => [...current, { id, message, tone }].slice(-MAX_VISIBLE));

    if (duration > 0) {
      timers.current.set(id, setTimeout(() => dismiss(id), duration));
    }
    return id;
  }, [dismiss]);

  // Every pending timer is cleared on unmount. Without this a timer fires
  // into an unmounted tree on a fast navigation.
  useEffect(() => {
    const pending = timers.current;
    return () => {
      pending.forEach(clearTimeout);
      pending.clear();
    };
  }, []);

  const value = useMemo(() => ({
    toast: push,
    success: (m, o) => push(m, { ...o, tone: 'success' }),
    error: (m, o) => push(m, { ...o, tone: 'error' }),
    info: (m, o) => push(m, { ...o, tone: 'info' }),
    dismiss,
  }), [push, dismiss]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      {createPortal(
        <div
          // `polite`, not `assertive`: a confirmation should not interrupt
          // whatever a screen reader is currently saying.
          role="status"
          aria-live="polite"
          className="pointer-events-none fixed inset-x-0 bottom-0 flex flex-col items-center gap-2 p-4 sm:inset-x-auto sm:bottom-4 sm:right-4 sm:items-end"
          style={{ zIndex: 'var(--z-toast)' }}
        >
          {toasts.map((t) => (
            <Toast key={t.id} {...t} onDismiss={() => dismiss(t.id)} />
          ))}
        </div>,
        document.body,
      )}
    </ToastContext.Provider>
  );
}

function Toast({ message, tone, onDismiss }) {
  const { icon: Icon, token, text } = TONES[tone] || TONES.info;

  return (
    <div className="surface-overlay slide-in-right pointer-events-auto flex w-full max-w-sm items-start gap-2.5 p-3 sm:w-auto sm:min-w-[16rem]">
      <span
        className="mt-px flex h-5 w-5 shrink-0 items-center justify-center rounded-md"
        style={{ background: `rgb(var(${token}) / 0.14)` }}
      >
        <Icon className="h-3.5 w-3.5" style={{ color: `rgb(var(${text}))` }} aria-hidden="true" />
      </span>
      <p className="flex-1 pt-px text-[0.8125rem] leading-snug text-ink-secondary">{message}</p>
      <button onClick={onDismiss} className="btn-ghost shrink-0 !p-1" aria-label="Dismiss">
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

/**
 * Raise a toast.
 *
 * Returns a no-op outside the provider rather than throwing. A missing
 * provider should not take down a page over a confirmation message.
 */
export function useToast() {
  return useContext(ToastContext) || {
    toast: () => {},
    success: () => {},
    error: () => {},
    info: () => {},
    dismiss: () => {},
  };
}
