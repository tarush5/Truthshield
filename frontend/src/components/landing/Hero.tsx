import gsap from 'gsap';
import { useEffect, useLayoutEffect, useRef, useState } from 'react';

import { Backdrop, HlsVideo } from '@/components/landing/HlsVideo';
import { ButtonLink, Button } from '@/components/ui';
import { scrollToSection } from '@/lib/scroll';
import { useAuth } from '@/stores/auth';

const ROLES = ['phishing', 'fraud', 'deepfakes', 'misinformation'];

export function Hero({ ready }: { ready: boolean }) {
  const root = useRef<HTMLElement>(null);
  const [role, setRole] = useState(0);
  const signedIn = useAuth((s) => Boolean(s.accessToken));

  useEffect(() => {
    const id = setInterval(() => setRole((r) => (r + 1) % ROLES.length), 2000);
    return () => clearInterval(id);
  }, []);

  // Entrance runs once the loading screen has gone, not behind it.
  useLayoutEffect(() => {
    if (!ready || !root.current) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const ctx = gsap.context(() => {
      const tl = gsap.timeline({ defaults: { ease: 'power3.out' } });
      tl.fromTo('.name-reveal', { opacity: 0, y: 50 }, { opacity: 1, y: 0, duration: 1.2, delay: 0.1 });
      tl.fromTo(
        '.blur-in',
        { opacity: 0, filter: 'blur(10px)', y: 20 },
        { opacity: 1, filter: 'blur(0px)', y: 0, duration: 1, stagger: 0.1, clearProps: 'filter' },
        0.3,
      );
    }, root);
    return () => ctx.revert();
  }, [ready]);

  return (
    <section id="home" ref={root} className="relative flex min-h-screen items-center justify-center overflow-hidden">
      <Backdrop />
      <HlsVideo />
      <div className="absolute inset-0 bg-black/20" aria-hidden />
      <div className="absolute bottom-0 left-0 right-0 h-48 bg-gradient-to-t from-bg to-transparent" aria-hidden />

      <div className="relative z-10 mx-auto flex max-w-5xl flex-col items-center px-6 pt-24 text-center">
        <p className="blur-in mb-8 text-xs uppercase tracking-[0.3em] text-muted">Digital trust intelligence · ’26</p>
        <h1 className="name-reveal mb-6 font-display text-5xl italic leading-[0.9] tracking-tight text-text-primary sm:text-6xl md:text-8xl lg:text-9xl">
          Verify before
          <br />
          you trust.
        </h1>
        <p className="blur-in mb-4 text-base text-text-primary/90 md:text-lg">
          Built to catch{' '}
          <span key={role} className="inline-block animate-role-fade-in font-display text-xl italic text-text-primary md:text-2xl">
            {ROLES[role]}
          </span>{' '}
          before it spreads.
        </p>
        <p className="blur-in mb-12 max-w-md text-sm text-muted md:text-base">
          Multimodal AI intelligence for detecting fraud, misinformation, manipulated media and suspicious digital content — with every conclusion traced to its evidence.
        </p>
        <div className="blur-in inline-flex flex-wrap justify-center gap-4">
          <ButtonLink to={signedIn ? '/app/investigate' : '/login'} state={{ from: '/app/investigate' }}>
            Start investigation
          </ButtonLink>
          <Button variant="outline" onClick={() => scrollToSection('#capabilities')}>
            Explore capabilities
          </Button>
        </div>
      </div>

      <div className="absolute bottom-8 left-1/2 z-10 hidden -translate-x-1/2 flex-col items-center gap-3 [@media(min-height:760px)]:flex" aria-hidden>
        <span className="text-xs uppercase tracking-[0.2em] text-muted">Scroll</span>
        <span className="relative h-10 w-px overflow-hidden bg-stroke">
          <span className="accent-gradient absolute inset-x-0 top-0 h-1/2 animate-scroll-down" />
        </span>
      </div>
    </section>
  );
}
