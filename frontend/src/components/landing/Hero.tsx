import { ArrowDown, ArrowLeft, ArrowRight } from 'lucide-react';
import { m } from 'motion/react';
import { useCallback, useEffect, useState } from 'react';

import { MessageCard } from '@/components/landing/CaseCards';
import { CASES } from '@/components/landing/cases';
import { PALETTE, pad } from '@/components/landing/palette';
import { cn } from '@/lib/format';
import { scrollToSection } from '@/lib/scroll';

const OFFSETS = [-2, -1, 0, 1, 2];
const AUTOPLAY_MS = 5500;

/**
 * A carousel of real example investigations. The whole hero takes the
 * active case's colour; neighbours fan out to either side.
 */
export function Hero() {
  const n = CASES.length;
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const go = useCallback((step: number) => setIndex((i) => (i + step + n) % n), [n]);

  useEffect(() => {
    if (paused || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const timer = window.setInterval(() => go(1), AUTOPLAY_MS);
    return () => window.clearInterval(timer);
  }, [go, paused]);

  const active = CASES[index];
  const p = PALETTE[active.colour];

  return (
    <section
      id="home"
      aria-roledescription="carousel"
      aria-label="Example investigations"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
      onKeyDown={(e) => {
        if (e.key === 'ArrowRight') go(1);
        if (e.key === 'ArrowLeft') go(-1);
      }}
      className="relative flex min-h-[100svh] flex-col overflow-hidden pt-24 transition-colors duration-700"
      style={{ background: p.bg, color: p.ink }}
    >
      <div
        aria-hidden
        className="absolute left-1/2 top-[42%] h-[44vmin] w-[44vmin] -translate-x-1/2 -translate-y-1/2 rounded-full transition-colors duration-700"
        style={{ background: p.soft, opacity: 0.55 }}
      />

      <div className="relative flex min-h-[300px] flex-1 items-center justify-center">
        {OFFSETS.map((offset) => {
          const k = (index + offset + n) % n;
          const far = Math.abs(offset) === 2;
          return (
            <m.button
              key={CASES[k].id}
              type="button"
              tabIndex={offset === 0 ? -1 : 0}
              aria-hidden={offset !== 0}
              aria-label={offset === 0 ? undefined : `Show ${CASES[k].title}`}
              onClick={() => offset !== 0 && go(offset)}
              className={cn('absolute', offset === 0 ? 'cursor-default' : 'hidden cursor-pointer md:block')}
              initial={false}
              animate={{
                x: `${offset * 23}vw`,
                y: offset === 0 ? 0 : far ? 40 : 18,
                rotate: offset === 0 ? -4 : offset * 9,
                scale: offset === 0 ? 1 : far ? 0.62 : 0.74,
                opacity: offset === 0 ? 1 : far ? 0.75 : 0.95,
                zIndex: 10 - Math.abs(offset),
              }}
              transition={{ type: 'spring', stiffness: 120, damping: 20 }}
            >
              <MessageCard c={CASES[k]} />
            </m.button>
          );
        })}
      </div>

      <div className="relative z-20 px-5 pb-4 text-center" aria-live="polite">
        <h2 className="font-display text-[clamp(48px,9vw,128px)] lowercase leading-[0.9]">{active.title}</h2>
        <p className="mt-3 text-sm font-semibold opacity-80">
          {pad(index + 1)} / {pad(n)} · {active.sub}
        </p>
        <div className="mt-5 flex items-center justify-center gap-4">
          <button
            type="button"
            onClick={() => go(-1)}
            aria-label="Previous example"
            className="flex h-11 w-11 items-center justify-center rounded-full border-2 border-current transition-transform hover:-translate-x-0.5"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div className="flex gap-1.5" role="tablist" aria-label="Choose an example">
            {CASES.map((c, i) => (
              <button
                key={c.id}
                type="button"
                role="tab"
                aria-selected={i === index}
                aria-label={c.title}
                onClick={() => setIndex(i)}
                className={cn('h-2 rounded-full bg-current transition-all duration-300', i === index ? 'w-7' : 'w-2 opacity-40 hover:opacity-70')}
              />
            ))}
          </div>
          <button
            type="button"
            onClick={() => go(1)}
            aria-label="Next example"
            className="flex h-11 w-11 items-center justify-center rounded-full border-2 border-current transition-transform hover:translate-x-0.5"
          >
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="relative z-20 flex flex-col items-start justify-between gap-5 px-5 pb-8 sm:flex-row sm:items-end sm:px-8 sm:pb-6">
        <h1 className="font-display max-w-[14ch] text-3xl leading-[0.95] sm:text-4xl">Verify before you trust. Then decide.</h1>
        <button
          type="button"
          onClick={() => scrollToSection('#catches')}
          className="flex items-center gap-2 rounded-full bg-[#FBF5EA] px-6 py-3 text-sm font-bold text-[#1D1A16] transition-transform duration-300 hover:-translate-y-0.5"
        >
          See what it catches <ArrowDown className="h-4 w-4" />
        </button>
      </div>
    </section>
  );
}
