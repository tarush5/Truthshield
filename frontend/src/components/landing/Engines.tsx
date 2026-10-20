import { ArrowUpRight } from 'lucide-react';
import { Link } from 'react-router-dom';

import { ORDER, PALETTE } from '@/components/landing/palette';
import { AVAILABILITY_LABEL, CAPABILITIES } from '@/lib/modules';
import { useAuth } from '@/stores/auth';

/** Every capability, coloured cards, each labelled with what is live today. */
export function Engines() {
  const signedIn = useAuth((s) => Boolean(s.accessToken));

  return (
    <section id="engines" aria-label="Engines" className="bg-bg px-4 py-24 sm:px-6 sm:py-32">
      <div className="mx-auto max-w-[1400px]">
        <div className="mb-12 flex flex-col justify-between gap-6 md:flex-row md:items-end">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-muted">The engines</p>
            <h2 className="font-display mt-3 text-[clamp(44px,7vw,96px)] leading-[0.9]">
              Every engine,
              <br />
              one report.
            </h2>
          </div>
          <p className="max-w-xs text-lg font-medium text-muted">Each card says what works today and what is still being built.</p>
        </div>

        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {CAPABILITIES.map((cap, i) => {
            const p = PALETTE[ORDER[i % ORDER.length]];
            return (
              <li key={cap.id}>
                <Link
                  to={signedIn ? cap.route : '/login'}
                  className="group flex h-full min-h-[300px] flex-col justify-between rounded-[32px] p-7 transition-transform duration-300 hover:-translate-y-1"
                  style={{ background: p.bg, color: p.ink }}
                >
                  <div className="flex items-start justify-between gap-3">
                    <span className="rounded-full border-2 border-current px-3 py-1 text-xs font-bold">
                      {AVAILABILITY_LABEL[cap.availability]}
                      {cap.availability !== 'live' && ` · Phase ${cap.phase}`}
                    </span>
                    <span className="flex h-10 w-10 items-center justify-center rounded-full bg-[#FBF5EA] text-[#1D1A16] transition-transform duration-300 group-hover:rotate-45">
                      <ArrowUpRight className="h-5 w-5" />
                    </span>
                  </div>
                  <div>
                    <h3 className="font-display text-3xl leading-[0.95]">{cap.title}</h3>
                    <p className="mt-3 text-[15px] font-medium leading-snug opacity-90">{cap.summary}</p>
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
