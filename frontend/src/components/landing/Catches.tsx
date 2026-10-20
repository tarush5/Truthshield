import { AnimatePresence, m } from 'motion/react';
import { useEffect, useRef, useState } from 'react';

import { BreakdownCard, MessageCard } from '@/components/landing/CaseCards';
import { BLURB, CASES } from '@/components/landing/cases';
import { PALETTE, pad } from '@/components/landing/palette';
import { RISK_STYLE, cn, humanize } from '@/lib/format';

/**
 * "What it catches": one screen per example, pinned while you scroll.
 *
 * Native sticky positioning and a passive scroll listener (one rAF per
 * frame at most) -- no animation library. The section is n screens tall;
 * which example shows is simply how far through it you are.
 */
export function Catches() {
  const ref = useRef<HTMLElement>(null);
  const n = CASES.length;
  const [active, setActive] = useState(0);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      const el = ref.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const travel = Math.max(1, rect.height - window.innerHeight);
      const p = Math.min(1, Math.max(0, -rect.top / travel));
      setProgress(p);
      setActive(Math.min(n - 1, Math.floor(p * n)));
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    update();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    return () => {
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
      cancelAnimationFrame(frame);
    };
  }, [n]);

  const jump = (i: number) => {
    const el = ref.current;
    if (!el) return;
    const travel = el.offsetHeight - window.innerHeight;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    window.scrollTo({ top: el.offsetTop + ((i + 0.5) / n) * travel, behavior: reduced ? 'auto' : 'smooth' });
  };

  const c = CASES[active];
  const p = PALETTE[c.colour];

  return (
    <section id="catches" ref={ref} aria-label="What TruthShield catches" style={{ height: `${n * 100}vh` }} className="relative">
      <div className="sticky top-0 flex h-[100svh] items-center overflow-hidden transition-colors duration-500" style={{ background: p.bg, color: p.ink }}>
        <div className="mx-auto grid w-full max-w-[1400px] items-center gap-8 px-5 pt-20 sm:px-8 lg:grid-cols-[1.05fr_1fr_1fr]">
          <AnimatePresence mode="wait">
            <m.div
              key={c.id}
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -16 }}
              transition={{ duration: 0.35 }}
            >
              <p className="text-xs font-bold uppercase tracking-[0.2em] opacity-80">
                {pad(active + 1)} — {c.sub}
              </p>
              <h2 className="font-display mt-3 text-[clamp(52px,8vw,120px)] lowercase leading-[0.88]">{c.title}</h2>
              <p className="mt-5 max-w-sm text-lg font-medium leading-snug">{BLURB[c.id]}</p>
              <ul className="mt-6 flex flex-wrap gap-2 text-sm font-semibold">
                <li className="rounded-full border-2 border-current px-3 py-1">risk {c.score}</li>
                <li className="rounded-full border-2 border-current px-3 py-1">{RISK_STYLE[c.level].label.toLowerCase()}</li>
                <li className="rounded-full border-2 border-current px-3 py-1">{humanize(c.classification).toLowerCase()}</li>
              </ul>
            </m.div>
          </AnimatePresence>

          <div className="relative hidden justify-center sm:flex">
            <AnimatePresence mode="wait">
              <m.div
                key={c.id}
                initial={{ opacity: 0, rotate: -14, y: 60 }}
                animate={{ opacity: 1, rotate: -6, y: 0 }}
                exit={{ opacity: 0, rotate: 4, y: -40 }}
                transition={{ type: 'spring', stiffness: 140, damping: 20 }}
              >
                <MessageCard c={c} />
              </m.div>
            </AnimatePresence>
          </div>

          <div className="hidden justify-center lg:flex">
            <AnimatePresence mode="wait">
              <m.div key={c.id} initial={{ opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} transition={{ duration: 0.4 }}>
                <BreakdownCard c={c} />
              </m.div>
            </AnimatePresence>
          </div>
        </div>

        <div className="absolute right-4 top-1/2 flex -translate-y-1/2 flex-col gap-3 sm:right-6" role="tablist" aria-label="Examples">
          {CASES.map((item, i) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={i === active}
              aria-label={item.title}
              onClick={() => jump(i)}
              className={cn('h-3.5 w-3.5 rounded-full border-2 transition-transform', i === active ? 'scale-125 border-current' : 'border-transparent hover:scale-110')}
              style={{ background: i === active ? 'transparent' : PALETTE[item.colour].bg, boxShadow: i === active ? 'none' : '0 0 0 1px rgba(29,26,22,0.25)' }}
            />
          ))}
        </div>

        <div className="absolute bottom-6 left-5 flex items-center gap-3 text-[11px] font-bold uppercase tracking-[0.2em] sm:left-8" aria-hidden>
          Scroll to explore
          <span className="relative h-0.5 w-24 overflow-hidden rounded-full" style={{ background: 'color-mix(in srgb, currentColor 25%, transparent)' }}>
            <span className="absolute inset-y-0 left-0 bg-current" style={{ width: `${Math.round(progress * 100)}%` }} />
          </span>
        </div>
      </div>
    </section>
  );
}
