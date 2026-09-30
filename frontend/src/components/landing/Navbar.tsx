import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { Logo } from '@/components/landing/Logo';
import { cn } from '@/lib/format';
import { scrollToSection } from '@/lib/scroll';
import { useAuth } from '@/stores/auth';

const LINKS = [
  { label: 'Home', target: '#home' },
  { label: 'Capabilities', target: '#capabilities' },
  { label: 'Pipeline', target: '#pipeline' },
];

export function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [active, setActive] = useState('#home');
  const signedIn = useAuth((s) => Boolean(s.accessToken));
  const navigate = useNavigate();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 100);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });

    // Active link follows whichever section crosses the middle of the viewport.
    const observer = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && setActive(`#${e.target.id}`)),
      { rootMargin: '-50% 0px -50% 0px' },
    );
    LINKS.forEach(({ target }) => {
      const el = document.querySelector(target);
      if (el) observer.observe(el);
    });
    return () => {
      window.removeEventListener('scroll', onScroll);
      observer.disconnect();
    };
  }, []);

  return (
    <header className="fixed left-0 right-0 top-0 z-50 flex justify-center px-4 pt-4 md:pt-6">
      <nav
        aria-label="Primary"
        className={cn(
          'inline-flex items-center rounded-full border border-white/10 bg-surface px-2 py-2 backdrop-blur-md transition-shadow',
          scrolled && 'shadow-md shadow-black/10',
        )}
      >
        <button onClick={() => scrollToSection(0)} aria-label="TruthShield — back to top" className="rounded-full">
          <Logo />
        </button>
        <span className="mx-1 hidden h-5 w-px bg-stroke sm:block" aria-hidden />
        {LINKS.map(({ label, target }) => (
          <button
            key={target}
            onClick={() => (target === '#home' ? scrollToSection(0) : scrollToSection(target))}
            aria-current={active === target ? 'true' : undefined}
            className={cn(
              'rounded-full px-3 py-1.5 text-xs transition-colors sm:px-4 sm:py-2 sm:text-sm',
              active === target ? 'bg-stroke/50 text-text-primary' : 'text-muted hover:bg-stroke/50 hover:text-text-primary',
            )}
          >
            {label}
          </button>
        ))}
        <span className="mx-1 hidden h-5 w-px bg-stroke sm:block" aria-hidden />
        {signedIn ? (
          <button onClick={() => navigate('/app')} className="group relative inline-flex rounded-full">
            <span aria-hidden className="accent-gradient absolute -inset-[2px] rounded-full opacity-0 transition-opacity group-hover:opacity-100" />
            <span className="relative rounded-full bg-surface px-3 py-1.5 text-xs text-text-primary backdrop-blur-md sm:px-4 sm:py-2 sm:text-sm">
              Open app ↗
            </span>
          </button>
        ) : (
          <Link to="/login" className="group relative inline-flex rounded-full">
            <span aria-hidden className="accent-gradient absolute -inset-[2px] rounded-full opacity-0 transition-opacity group-hover:opacity-100" />
            <span className="relative rounded-full bg-surface px-3 py-1.5 text-xs text-text-primary backdrop-blur-md sm:px-4 sm:py-2 sm:text-sm">
              Sign in ↗
            </span>
          </Link>
        )}
      </nav>
    </header>
  );
}
