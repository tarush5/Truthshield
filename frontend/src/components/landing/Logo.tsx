import { cn } from '@/lib/format';

/** The monogram: cream "ts" on an ink disc. */
export function Logo({ className, size = 'md' }: { className?: string; size?: 'sm' | 'md' }) {
  const dim = size === 'sm' ? 'h-8 w-8 text-[13px]' : 'h-9 w-9 text-[14px]';
  return (
    <span
      aria-hidden
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded-full bg-text-primary font-display text-bg transition-transform duration-300 hover:-rotate-6',
        dim,
        className,
      )}
    >
      ts
    </span>
  );
}

/** The lowercase wordmark. */
export function Wordmark({ className }: { className?: string }) {
  return <span className={cn('font-display tracking-[-0.05em]', className)}>truthshield</span>;
}
