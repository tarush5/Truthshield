import gsap from 'gsap';
import { ArrowRight } from 'lucide-react';
import { useLayoutEffect, useRef } from 'react';

import { Backdrop, HlsVideo } from '@/components/landing/HlsVideo';
import { ButtonLink } from '@/components/ui';
import { useHealth } from '@/hooks/queries';
import { API_BASE } from '@/lib/api';
import { cn } from '@/lib/format';
import { useAuth } from '@/stores/auth';

const PHRASE = 'VERIFY BEFORE YOU TRUST • ';
const LINKS = [
  { label: 'GitHub', href: 'https://github.com/tarush5/Truthshield' },
  { label: 'API docs', href: API_BASE.replace(/\/api\/v1$/, '') + '/docs' },
  { label: 'Architecture', href: 'https://github.com/tarush5/Truthshield/blob/main/ARCHITECTURE.md' },
  { label: 'Security', href: 'https://github.com/tarush5/Truthshield/blob/main/docs/MIGRATION.md#15-security-findings' },
];

function SystemStatus() {
  const { data, isError, isLoading } = useHealth();
  const state = isLoading ? 'checking' : isError || !data ? 'down' : data.status === 'ok' ? 'ok' : 'degraded';
  const label = {
    checking: 'Checking system status…',
    ok: 'All systems operational',
    degraded: 'Operational — running with reduced evidence sources',
    down: 'API unreachable',
  }[state];
  const dot = { checking: 'bg-muted', ok: 'bg-emerald-400', degraded: 'bg-risk-medium', down: 'bg-risk-critical' }[state];

  return (
    <span className="flex items-center gap-2 text-sm text-muted" role="status">
      <span className="relative flex h-2 w-2">
        {state === 'ok' && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />}
        <span className={cn('relative inline-flex h-2 w-2 rounded-full', dot)} />
      </span>
      {label}
    </span>
  );
}

export function Contact() {
  const track = useRef<HTMLDivElement>(null);
  const signedIn = useAuth((s) => Boolean(s.accessToken));

  useLayoutEffect(() => {
    if (!track.current || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const tween = gsap.to(track.current, { xPercent: -50, duration: 40, ease: 'none', repeat: -1 });
    return () => {
      tween.kill();
    };
  }, []);

  return (
    <footer id="contact" className="relative overflow-hidden bg-bg pb-8 pt-16 md:pb-12 md:pt-20">
      <Backdrop />
      <HlsVideo flip />
      <div className="absolute inset-0 bg-black/60" aria-hidden />
      <div className="absolute left-0 right-0 top-0 h-40 bg-gradient-to-b from-bg to-transparent" aria-hidden />

      <div className="relative z-10">
        <div className="overflow-hidden whitespace-nowrap py-6" aria-hidden>
          <div ref={track} className="inline-block font-display text-6xl italic text-text-primary/90 md:text-8xl">
            {PHRASE.repeat(10)}
          </div>
        </div>

        <div className="mx-auto flex max-w-[1200px] flex-col items-center px-6 py-16 text-center md:px-10 md:py-24">
          <p className="mb-6 text-xs uppercase tracking-[0.3em] text-muted">Something feels off?</p>
          <h2 className="text-4xl font-medium tracking-tight text-text-primary md:text-6xl">
            Don't guess. <span className="font-display italic">Investigate it.</span>
          </h2>
          <ButtonLink to={signedIn ? '/app/investigate' : '/login'} className="mt-10">
            Start an investigation <ArrowRight className="h-4 w-4" aria-hidden />
          </ButtonLink>
        </div>

        <div className="mx-auto flex max-w-[1200px] flex-col items-center justify-between gap-6 border-t border-white/10 px-6 pt-8 md:flex-row md:px-10 lg:px-16">
          <nav aria-label="Footer" className="flex flex-wrap justify-center gap-6">
            {LINKS.map((l) => (
              <a key={l.label} href={l.href} target="_blank" rel="noreferrer" className="text-sm text-muted transition-colors hover:text-text-primary">
                {l.label}
              </a>
            ))}
          </nav>
          <SystemStatus />
        </div>
        <p className="mx-auto mt-6 max-w-[1200px] px-6 text-center text-xs text-muted/70 md:px-10 md:text-left lg:px-16">
          Assessments are automated and can be wrong. They show signals and evidence, not proof.
        </p>
      </div>
    </footer>
  );
}
