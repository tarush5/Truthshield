import { Link } from 'react-router-dom';

import { Wordmark } from '@/components/landing/Logo';
import { scrollToSection } from '@/lib/scroll';
import { useAuth } from '@/stores/auth';

const LINKS = [
  { label: 'Threats', target: '#catches' },
  { label: 'Why us', target: '#why' },
  { label: 'Engines', target: '#engines' },
  { label: 'FAQ', target: '#faq' },
];

export function Navbar() {
  const signedIn = useAuth((s) => Boolean(s.accessToken));

  return (
    <header className="fixed inset-x-3 top-3 z-50 sm:inset-x-4 sm:top-4">
      <nav
        aria-label="Primary"
        className="relative mx-auto flex h-14 max-w-[1400px] items-center justify-between rounded-full bg-[#FBF5EA] px-3 text-[#1D1A16] shadow-[0_8px_30px_-12px_rgba(29,26,22,0.25)] sm:px-4"
      >
        <ul className="hidden items-center gap-1 md:flex">
          {LINKS.map((link) => (
            <li key={link.target}>
              <a
                href={link.target}
                onClick={(e) => {
                  e.preventDefault();
                  scrollToSection(link.target);
                }}
                className="rounded-full px-3 py-2 text-sm font-semibold transition-colors hover:bg-[#1D1A16]/5"
              >
                {link.label}
              </a>
            </li>
          ))}
        </ul>

        <Link
          to="/"
          onClick={() => scrollToSection(0)}
          aria-label="TruthShield, back to top"
          className="pl-2 text-2xl md:absolute md:left-1/2 md:-translate-x-1/2 md:pl-0"
        >
          <Wordmark />
        </Link>

        <Link
          to={signedIn ? '/app' : '/login'}
          className="rounded-full bg-[#1D1A16] px-5 py-2.5 text-sm font-semibold text-[#FBF5EA] transition-transform duration-300 hover:-translate-y-0.5"
        >
          {signedIn ? 'Open the app' : 'Sign in'}
        </Link>
      </nav>
    </header>
  );
}
