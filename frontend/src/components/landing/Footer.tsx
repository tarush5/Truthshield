import { Link } from 'react-router-dom';

import { useHealth } from '@/hooks/queries';
import { API_BASE } from '@/lib/api';
import { cn } from '@/lib/format';
import { scrollToSection } from '@/lib/scroll';
import { useAuth } from '@/stores/auth';

const EXPLORE = [
  { label: 'Threats', target: '#catches' },
  { label: 'Why us', target: '#why' },
  { label: 'Engines', target: '#engines' },
  { label: 'FAQ', target: '#faq' },
];

const PROJECT = [
  { label: 'GitHub', href: 'https://github.com/tarush5/Truthshield' },
  { label: 'API docs', href: API_BASE.replace(/\/api\/v1$/, '') + '/docs' },
  { label: 'Architecture', href: 'https://github.com/tarush5/Truthshield/blob/main/ARCHITECTURE.md' },
  { label: 'Roadmap', href: 'https://github.com/tarush5/Truthshield/blob/main/docs/ROADMAP.md' },
];

/** Live, from /system/health: never a hard-coded "all good". */
function SystemStatus() {
  const { data, isError, isLoading } = useHealth();
  const state = isLoading ? 'checking' : isError || !data ? 'down' : data.status === 'ok' ? 'ok' : 'degraded';
  const label = {
    checking: 'Checking status…',
    ok: 'All systems operational',
    degraded: 'Running with reduced evidence sources',
    down: 'API unreachable',
  }[state];
  const dot = { checking: 'bg-[#FBF5EA]/40', ok: 'bg-brand-green', degraded: 'bg-brand-amber', down: 'bg-brand-orange' }[state];
  return (
    <span className="flex items-center gap-2 text-sm font-medium text-[#FBF5EA]/80" role="status">
      <span className={cn('h-2.5 w-2.5 rounded-full', dot)} />
      {label}
    </span>
  );
}

export function Footer() {
  const signedIn = useAuth((s) => Boolean(s.accessToken));

  return (
    <footer id="contact" className="overflow-hidden bg-[#1D1A16] px-4 pt-20 text-[#FBF5EA] sm:px-6">
      <div className="mx-auto grid max-w-[1400px] gap-12 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
        <div>
          <p className="font-display text-4xl leading-[0.95]">
            Verify before
            <br />
            you trust.
          </p>
          <Link
            to={signedIn ? '/app' : '/login'}
            className="mt-6 inline-flex rounded-full bg-[#FBF5EA] px-6 py-3 text-sm font-bold text-[#1D1A16] transition-transform duration-300 hover:-translate-y-0.5"
          >
            {signedIn ? 'Open the app' : 'Sign in'}
          </Link>
        </div>
        <nav aria-label="Explore">
          <p className="mb-4 text-xs font-bold uppercase tracking-[0.2em] text-[#FBF5EA]/60">Explore</p>
          <ul className="space-y-2.5 font-medium">
            {EXPLORE.map((l) => (
              <li key={l.target}>
                <a
                  href={l.target}
                  onClick={(e) => {
                    e.preventDefault();
                    scrollToSection(l.target);
                  }}
                  className="hover:text-brand-amber"
                >
                  {l.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <nav aria-label="Project">
          <p className="mb-4 text-xs font-bold uppercase tracking-[0.2em] text-[#FBF5EA]/60">Project</p>
          <ul className="space-y-2.5 font-medium">
            {PROJECT.map((l) => (
              <li key={l.label}>
                <a href={l.href} target="_blank" rel="noreferrer" className="hover:text-brand-amber">
                  {l.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <div>
          <p className="mb-4 text-xs font-bold uppercase tracking-[0.2em] text-[#FBF5EA]/60">Status</p>
          <SystemStatus />
          <p className="mt-4 text-sm font-medium text-[#FBF5EA]/60">Report cyber fraud in India: call 1930 or visit cybercrime.gov.in.</p>
        </div>
      </div>

      <p aria-hidden className="font-display mx-auto mt-16 max-w-[1400px] select-none whitespace-nowrap text-center text-[clamp(64px,17vw,280px)] leading-[0.78] tracking-[-0.06em]">
        truthshield
      </p>
      <div className="mx-auto flex max-w-[1400px] flex-wrap justify-between gap-3 border-t border-[#FBF5EA]/15 py-6 text-xs font-medium text-[#FBF5EA]/60">
        <span>© 2026 TruthShield · MIT licence</span>
        <span>Every number on this page comes from the engines or the code.</span>
      </div>
    </footer>
  );
}
