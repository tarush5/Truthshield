import { cn } from '@/lib/format';

/** The accent-ring monogram. The gradient reverses direction on hover. */
export function Logo({ className, size = 'md' }: { className?: string; size?: 'sm' | 'md' }) {
  const dim = size === 'sm' ? 'h-8 w-8 text-[12px]' : 'h-9 w-9 text-[13px]';
  return (
    <span className={cn('group/logo relative inline-flex shrink-0 rounded-full transition-transform duration-300 hover:scale-110', dim, className)}>
      <span aria-hidden className="accent-gradient absolute inset-0 rounded-full transition-opacity duration-300 group-hover/logo:opacity-0" />
      <span aria-hidden className="accent-gradient-reverse absolute inset-0 rounded-full opacity-0 transition-opacity duration-300 group-hover/logo:opacity-100" />
      <span className="absolute inset-[2px] flex items-center justify-center rounded-full bg-bg font-display italic text-text-primary">
        TS
      </span>
    </span>
  );
}
