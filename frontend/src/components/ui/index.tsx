import { Loader2 } from 'lucide-react';
import type { ButtonHTMLAttributes, HTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react';
import { forwardRef } from 'react';
import { Link, type LinkProps } from 'react-router-dom';

import { cn } from '@/lib/format';

/* ── Buttons ──────────────────────────────────────────────────
   The portfolio pattern: a gradient ring sits behind the button at -2px
   and fades in on hover, so the border animates without layout shift. */

type Variant = 'solid' | 'outline' | 'pill';
type Size = 'sm' | 'md';

const inner: Record<Variant, string> = {
  solid: 'bg-text-primary text-bg group-hover:bg-bg group-hover:text-text-primary',
  outline: 'border-2 border-stroke bg-bg text-text-primary group-hover:border-transparent',
  pill: 'bg-surface text-text-primary backdrop-blur-md',
};

const sizes: Record<Size, string> = {
  sm: 'px-4 py-2 text-xs sm:text-sm',
  md: 'px-7 py-3.5 text-sm',
};

function RingContent({ variant, size, children, className }: { variant: Variant; size: Size; children: ReactNode; className?: string }) {
  return (
    <>
      <span aria-hidden className="accent-gradient absolute -inset-[2px] rounded-full opacity-0 transition-opacity duration-300 group-hover:opacity-100 group-focus-visible:opacity-100" />
      <span className={cn('relative inline-flex items-center gap-2 rounded-full font-medium transition-colors duration-300', inner[variant], sizes[size], className)}>
        {children}
      </span>
    </>
  );
}

const outer = 'group relative inline-flex rounded-full transition-transform duration-300 hover:scale-105 disabled:pointer-events-none disabled:opacity-50 focus-visible:outline-none';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  innerClassName?: string;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'solid', size = 'md', loading, children, className, innerClassName, disabled, ...rest },
  ref,
) {
  return (
    <button ref={ref} className={cn(outer, className)} disabled={disabled || loading} {...rest}>
      <RingContent variant={variant} size={size} className={innerClassName}>
        {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
        {children}
      </RingContent>
    </button>
  );
});

interface ButtonLinkProps extends LinkProps {
  variant?: Variant;
  size?: Size;
}

export function ButtonLink({ variant = 'solid', size = 'md', children, className, ...rest }: ButtonLinkProps) {
  return (
    <Link className={cn(outer, className)} {...rest}>
      <RingContent variant={variant} size={size}>{children as ReactNode}</RingContent>
    </Link>
  );
}

export function IconButton({ className, children, ...rest }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={cn('inline-flex h-9 w-9 items-center justify-center rounded-full text-muted transition-colors hover:bg-stroke/60 hover:text-text-primary disabled:opacity-40', className)}
      {...rest}
    >
      {children}
    </button>
  );
}

/* ── Surfaces ─────────────────────────────────────────────── */

export function Card({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('rounded-3xl border border-stroke bg-surface/60', className)} {...rest} />;
}

export function CardHeader({ title, eyebrow, action, className }: { title: ReactNode; eyebrow?: string; action?: ReactNode; className?: string }) {
  return (
    <div className={cn('flex items-start justify-between gap-4 px-5 pt-5 sm:px-6 sm:pt-6', className)}>
      <div className="min-w-0">
        {eyebrow && <p className="mb-1 text-[11px] uppercase tracking-[0.25em] text-muted">{eyebrow}</p>}
        <h2 className="text-base font-medium text-text-primary">{title}</h2>
      </div>
      {action}
    </div>
  );
}

export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('flex items-center gap-3', className)}>
      <span className="h-px w-8 bg-stroke" aria-hidden />
      <span className="text-xs uppercase tracking-[0.3em] text-muted">{children}</span>
    </div>
  );
}

export function Badge({ children, className, tone = 'neutral', title }: { children: ReactNode; className?: string; tone?: 'neutral' | 'accent' | 'good' | 'warn' | 'bad'; title?: string }) {
  const tones = {
    neutral: 'border-stroke bg-stroke/40 text-muted',
    accent: 'border-[#4E85BF]/40 bg-[#4E85BF]/10 text-[#9fbcdb]',
    good: 'border-risk-low/40 bg-risk-low/10 text-risk-low',
    warn: 'border-risk-medium/40 bg-risk-medium/10 text-risk-medium',
    bad: 'border-risk-critical/50 bg-risk-critical/10 text-[#e08a90]',
  } as const;
  return (
    <span title={title} className={cn('inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-[11px] font-medium', tones[tone], className)}>
      {children}
    </span>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn('h-4 w-4 animate-spin text-muted', className)} aria-label="Loading" />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-2xl bg-stroke/50', className)} aria-hidden />;
}

export function EmptyState({ title, body, action, icon }: { title: string; body?: ReactNode; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-3xl border border-dashed border-stroke px-6 py-14 text-center">
      {icon && <div className="mb-4 text-muted">{icon}</div>}
      <p className="font-display text-2xl italic text-text-primary">{title}</p>
      {body && <div className="mt-2 max-w-md text-sm text-muted">{body}</div>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}

export function ErrorNotice({ error, className }: { error: unknown; className?: string }) {
  const message = error instanceof Error ? error.message : 'Something went wrong.';
  const requestId = (error as { requestId?: string | null })?.requestId;
  return (
    <div role="alert" className={cn('rounded-2xl border border-risk-critical/40 bg-risk-critical/10 px-4 py-3 text-sm text-[#e8a2a7]', className)}>
      {message}
      {requestId && <span className="mt-1 block font-mono text-[11px] text-muted">Request ID {requestId}</span>}
    </div>
  );
}

/* ── Form fields ──────────────────────────────────────────── */

const field = 'w-full rounded-2xl border border-stroke bg-bg px-4 py-3 text-sm text-text-primary placeholder:text-muted/70 transition-colors focus:border-[#4E85BF]/60 focus:outline-none focus:ring-2 focus:ring-[#4E85BF]/25';

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input({ className, ...rest }, ref) {
  return <input ref={ref} className={cn(field, className)} {...rest} />;
});

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea({ className, ...rest }, ref) {
  return <textarea ref={ref} className={cn(field, 'resize-y leading-relaxed', className)} {...rest} />;
});

export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cn(field, 'appearance-none bg-[length:12px] pr-9', className)} {...rest}>
      {children}
    </select>
  );
}

export function Label({ children, htmlFor, hint }: { children: ReactNode; htmlFor?: string; hint?: ReactNode }) {
  return (
    <label htmlFor={htmlFor} className="mb-2 flex items-baseline justify-between gap-3 text-xs font-medium text-muted">
      <span className="uppercase tracking-[0.2em]">{children}</span>
      {hint && <span className="normal-case tracking-normal text-muted/80">{hint}</span>}
    </label>
  );
}

/* ── Tabs ─────────────────────────────────────────────────── */

export function Tabs<T extends string>({ tabs, value, onChange, label }: { tabs: { id: T; label: string; count?: number }[]; value: T; onChange: (id: T) => void; label: string }) {
  return (
    <div role="tablist" aria-label={label} className="scrollbar-none -mx-1 flex gap-1 overflow-x-auto px-1">
      {tabs.map((tab) => {
        const active = tab.id === value;
        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(tab.id)}
            className={cn(
              'whitespace-nowrap rounded-full px-4 py-2 text-sm transition-colors',
              active ? 'bg-stroke/70 text-text-primary' : 'text-muted hover:bg-stroke/40 hover:text-text-primary',
            )}
          >
            {tab.label}
            {tab.count !== undefined && <span className="ml-1.5 text-xs text-muted tabular">{tab.count}</span>}
          </button>
        );
      })}
    </div>
  );
}

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow: string; title: ReactNode; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-8 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <Eyebrow className="mb-4">{eyebrow}</Eyebrow>
        <h1 className="text-3xl font-medium tracking-tight text-text-primary sm:text-4xl">{title}</h1>
        {description && <p className="mt-3 max-w-2xl text-sm text-muted sm:text-base">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-3">{actions}</div>}
    </div>
  );
}
