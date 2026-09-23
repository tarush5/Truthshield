import React, { useCallback, useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

/**
 * Overlay primitives: Modal, Dropdown, Tooltip.
 *
 * Hand-built rather than pulled in. A headless overlay library is ~15kB
 * gzipped and this app needs three of its components, none of which are
 * doing anything exotic. What they do need is the accessibility, so that is
 * what is implemented carefully here:
 *
 *   * Escape closes, and a click outside closes.
 *   * A modal traps Tab, restores focus to whatever opened it, and marks
 *     the rest of the page `aria-hidden`.
 *   * Body scroll is locked while a modal is open, including on iOS, where
 *     `overflow: hidden` alone does not hold.
 *   * Everything is portalled to `body`, so a parent's `overflow: hidden`
 *     or `transform` cannot clip it -- the single most common way a
 *     hand-rolled dropdown breaks.
 */

/** Escape, once, for whichever overlay is on top. */
function useEscape(active, onEscape) {
  useEffect(() => {
    if (!active) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onEscape();
      }
    };
    document.addEventListener('keydown', onKey, true);
    return () => document.removeEventListener('keydown', onKey, true);
  }, [active, onEscape]);
}

/** A pointer press anywhere outside `ref`. */
function useOutsideClick(active, ref, onOutside) {
  useEffect(() => {
    if (!active) return undefined;
    const onDown = (e) => {
      if (ref.current && !ref.current.contains(e.target)) onOutside();
    };
    // `mousedown`, not `click`: a click fires after the press has already
    // moved focus, which makes the close feel late.
    document.addEventListener('mousedown', onDown);
    document.addEventListener('touchstart', onDown, { passive: true });
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('touchstart', onDown);
    };
  }, [active, ref, onOutside]);
}

/**
 * Hold the page still behind an overlay.
 *
 * The scrollbar is compensated with padding, or the page shifts sideways as
 * it disappears -- a jump that reads as a bug every time.
 */
function useScrollLock(active) {
  useEffect(() => {
    if (!active) return undefined;
    const { body } = document;
    const previousOverflow = body.style.overflow;
    const previousPadding = body.style.paddingRight;
    const gap = window.innerWidth - document.documentElement.clientWidth;

    body.style.overflow = 'hidden';
    if (gap > 0) body.style.paddingRight = `${gap}px`;
    return () => {
      body.style.overflow = previousOverflow;
      body.style.paddingRight = previousPadding;
    };
  }, [active]);
}

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])';

/* ── Modal ────────────────────────────────────────────────── */

export function Modal({ open, onClose, title, description, children, footer, size = 'md' }) {
  const panelRef = useRef(null);
  const returnFocusRef = useRef(null);
  const titleId = useId();
  const descriptionId = useId();

  useEscape(open, onClose);
  useScrollLock(open);

  // Remember what had focus, move into the dialog, and put it back on close.
  // Without the restore, closing a modal drops focus onto <body> and a
  // keyboard user starts again from the top of the page.
  useEffect(() => {
    if (!open) return undefined;
    returnFocusRef.current = document.activeElement;
    const first = panelRef.current?.querySelector(FOCUSABLE);
    (first || panelRef.current)?.focus();
    return () => returnFocusRef.current?.focus?.();
  }, [open]);

  // Keep Tab inside the dialog.
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key !== 'Tab' || !panelRef.current) return;
      const items = [...panelRef.current.querySelectorAll(FOCUSABLE)].filter(
        (el) => el.offsetParent !== null,
      );
      if (!items.length) return;

      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  if (!open) return null;

  const width = { sm: 'max-w-sm', md: 'max-w-lg', lg: 'max-w-2xl' }[size] || 'max-w-lg';

  return createPortal(
    <div
      className="fixed inset-0 flex items-end justify-center p-0 sm:items-center sm:p-6"
      style={{ zIndex: 'var(--z-modal)' }}
    >
      <div className="scrim" onClick={onClose} aria-hidden="true" />

      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        aria-describedby={description ? descriptionId : undefined}
        tabIndex={-1}
        // Full-width sheet on a phone, centred panel above it. A centred
        // card on a 375px screen wastes the edges and puts the actions
        // further from the thumb.
        className={`surface-overlay slide-up relative w-full ${width} !rounded-b-none sm:!rounded-2xl`}
      >
        {(title || onClose) && (
          <header className="flex items-start justify-between gap-4 border-b border-line p-5">
            <div className="min-w-0">
              {title && (
                <h2 id={titleId} className="text-[0.9375rem] font-semibold text-ink">
                  {title}
                </h2>
              )}
              {description && (
                <p id={descriptionId} className="mt-1 text-[0.8125rem] leading-relaxed text-ink-muted">
                  {description}
                </p>
              )}
            </div>
            <button onClick={onClose} className="btn-ghost !p-1.5" aria-label="Close">
              <X className="h-4 w-4" />
            </button>
          </header>
        )}

        <div className="max-h-[70vh] overflow-y-auto p-5">{children}</div>

        {footer && (
          <footer className="flex items-center justify-end gap-2 border-t border-line p-4">
            {footer}
          </footer>
        )}
      </div>
    </div>,
    document.body,
  );
}

/* ── Dropdown ─────────────────────────────────────────────── */

/**
 * A menu anchored to its trigger.
 *
 * Positioned from the trigger's measured rect and portalled to `body`, so
 * it is never clipped by an ancestor and never fights a stacking context.
 * It flips above the trigger when there is not room below.
 */
export function Dropdown({ trigger, children, align = 'end', width = 200 }) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState(null);
  const triggerRef = useRef(null);
  const menuRef = useRef(null);

  const close = useCallback(() => setOpen(false), []);
  useEscape(open, close);
  useOutsideClick(open, menuRef, (e) => {
    // The trigger handles its own toggle; closing here too would reopen it.
    if (!triggerRef.current?.contains(e?.target)) close();
  });

  const place = useCallback(() => {
    const rect = triggerRef.current?.getBoundingClientRect();
    if (!rect) return;

    const spaceBelow = window.innerHeight - rect.bottom;
    const flip = spaceBelow < 240 && rect.top > spaceBelow;
    setPosition({
      top: flip ? undefined : rect.bottom + 6,
      bottom: flip ? window.innerHeight - rect.top + 6 : undefined,
      left: align === 'start'
        ? Math.max(8, rect.left)
        : Math.max(8, Math.min(rect.right - width, window.innerWidth - width - 8)),
      flip,
    });
  }, [align, width]);

  useEffect(() => {
    if (!open) return undefined;
    place();
    // Reposition rather than trying to follow: a menu that drifts away from
    // its trigger on scroll is worse than one that simply stays put.
    window.addEventListener('resize', place);
    window.addEventListener('scroll', close, true);
    return () => {
      window.removeEventListener('resize', place);
      window.removeEventListener('scroll', close, true);
    };
  }, [open, place, close]);

  return (
    <>
      <span ref={triggerRef} className="contents">
        {React.cloneElement(trigger, {
          onClick: (e) => {
            trigger.props.onClick?.(e);
            setOpen((v) => !v);
          },
          'aria-expanded': open,
          'aria-haspopup': 'menu',
        })}
      </span>

      {open && position && createPortal(
        <div
          ref={menuRef}
          role="menu"
          className="surface-overlay pop fixed p-1.5"
          style={{
            top: position.top,
            bottom: position.bottom,
            left: position.left,
            width,
            zIndex: 'var(--z-dropdown)',
            '--pop-origin': position.flip ? 'bottom' : 'top',
          }}
          onClick={close}
        >
          {children}
        </div>,
        document.body,
      )}
    </>
  );
}

/* ── Tooltip ──────────────────────────────────────────────── */

/**
 * A hint on hover, and on keyboard focus.
 *
 * The focus half matters: a tooltip that only appears on hover is invisible
 * to anyone navigating by keyboard, which is usually the person who most
 * needed the hint.
 */
export function Tooltip({ label, children, side = 'top' }) {
  const [shown, setShown] = useState(false);
  const id = useId();

  const position = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-1.5',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-1.5',
    left: 'right-full top-1/2 -translate-y-1/2 mr-1.5',
    right: 'left-full top-1/2 -translate-y-1/2 ml-1.5',
  }[side];

  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setShown(true)}
      onMouseLeave={() => setShown(false)}
      onFocus={() => setShown(true)}
      onBlur={() => setShown(false)}
    >
      {React.cloneElement(children, { 'aria-describedby': shown ? id : undefined })}
      {shown && (
        <span id={id} role="tooltip" className={`tooltip ${position}`}>
          {label}
        </span>
      )}
    </span>
  );
}
