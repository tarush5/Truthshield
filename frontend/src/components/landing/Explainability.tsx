import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { X } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useLayoutEffect, useRef, useState } from 'react';

import { ButtonLink, Eyebrow } from '@/components/ui';
import { cn } from '@/lib/format';
import { useAuth } from '@/stores/auth';

gsap.registerPlugin(ScrollTrigger);

interface Item {
  kicker: string;
  title: string;
  meta: string;
  tone: 'critical' | 'high' | 'medium' | 'neutral' | 'accent';
  detail: string;
  rotate: number;
}

// Taken from the synthetic demo samples' real output -- labelled as such.
const ITEMS: Item[] = [
  { kicker: '+46 points', title: "Lookalike of 'paypal'", meta: 'URL · Heuristic · url 1.0.0', tone: 'critical', rotate: -4,
    detail: "The registered name 'paypa1-account-security.click' is one character away from 'paypal'. The evidence field quotes the domain and its similarity score (0.83), so the finding can be checked by hand." },
  { kicker: '+37 points', title: 'Bank impersonation', meta: 'Language · Heuristic · text 1.0.0', tone: 'high', rotate: 3,
    detail: 'Matched on the exact phrase "aapka SBI account aaj band ho jayega" — Hinglish, which an English-only rule set would score at zero.' },
  { kicker: 'Confidence 0.61', title: 'Capped: heuristics only', meta: 'Risk engine · confidence axis', tone: 'accent', rotate: -2,
    detail: 'Risk and confidence are separate. With no retrieved or model-based corroboration, confidence is capped — "looks bad, not certain" is a real state and is shown as one.' },
  { kicker: 'Skipped', title: 'EVIDENCE_RETRIEVAL', meta: 'Timeline · evidence engine', tone: 'neutral', rotate: 4,
    detail: 'In offline mode the timeline records the stage as skipped with its reason, and every claim is marked NOT_CHECKED — never "unsupported".' },
  { kicker: 'Not assessed', title: 'Reputation family', meta: 'Risk breakdown', tone: 'medium', rotate: -3,
    detail: 'No threat-intelligence provider is configured, so the reputation family contributes nothing — and says so, instead of showing a reassuring zero.' },
  { kicker: 'SHA-256', title: 'b79d295e…3899', meta: 'Input · typosquat demo', tone: 'neutral', rotate: 2,
    detail: 'Every input is hashed at intake and re-verified in the HASHING stage. Predictions are stored against the hash and engine version, so a result can be reproduced.' },
];

const TONE: Record<Item['tone'], string> = {
  critical: 'text-risk-critical',
  high: 'text-risk-high',
  medium: 'text-risk-medium',
  accent: 'accent-text',
  neutral: 'text-muted',
};

function SignalCard({ item, onOpen }: { item: Item; onOpen: () => void }) {
  return (
    <button
      onClick={onOpen}
      style={{ rotate: `${item.rotate}deg` }}
      className="pointer-events-auto flex aspect-square w-full max-w-[320px] flex-col justify-between rounded-3xl border border-stroke bg-surface p-6 text-left shadow-2xl shadow-black/40 transition-transform duration-300 hover:scale-[1.03]"
    >
      <span className={cn('text-sm font-medium tabular', TONE[item.tone])}>{item.kicker}</span>
      <span className="font-display text-3xl italic leading-tight text-text-primary">{item.title}</span>
      <span className="text-xs uppercase tracking-[0.15em] text-muted">{item.meta}</span>
    </button>
  );
}

export function Explainability() {
  const section = useRef<HTMLElement>(null);
  const content = useRef<HTMLDivElement>(null);
  const left = useRef<HTMLDivElement>(null);
  const right = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState<Item | null>(null);
  const signedIn = useAuth((s) => Boolean(s.accessToken));

  useLayoutEffect(() => {
    if (!section.current) return;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const ctx = gsap.context(() => {
      ScrollTrigger.create({
        trigger: section.current,
        start: 'top top',
        end: 'bottom bottom',
        pin: content.current,
        pinSpacing: false,
      });
      if (!reduced) {
        const scrub = { trigger: section.current, start: 'top bottom', end: 'bottom top', scrub: true };
        gsap.fromTo(left.current, { y: 120 }, { y: -260, ease: 'none', scrollTrigger: scrub });
        gsap.fromTo(right.current, { y: 320 }, { y: -120, ease: 'none', scrollTrigger: { ...scrub } });
      }
    }, section);
    // Images and fonts above change the section's offset after mount.
    const refresh = setTimeout(() => ScrollTrigger.refresh(), 600);
    return () => {
      clearTimeout(refresh);
      ctx.revert();
    };
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(null);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  const columns = [ITEMS.filter((_, i) => i % 2 === 0), ITEMS.filter((_, i) => i % 2 === 1)];

  return (
    <section ref={section} className="relative min-h-[300vh] bg-bg" aria-label="Explainability">
      <div ref={content} className="relative z-10 flex h-screen flex-col items-center justify-center px-6 text-center">
        <Eyebrow className="mb-6">Explainability</Eyebrow>
        <h2 className="text-5xl font-medium tracking-tight text-text-primary md:text-7xl">
          Explainable by <span className="font-display italic">design</span>
        </h2>
        <p className="mt-5 max-w-md text-sm text-muted md:text-base">
          The cards are real output from the synthetic demo samples. Every score comes apart into signals like these.
        </p>
        <ButtonLink to={signedIn ? '/app/investigate' : '/login'} variant="outline" size="sm" className="mt-8">
          Run a demo investigation
        </ButtonLink>
      </div>

      <div className="pointer-events-none absolute inset-0 z-20">
        <div className="mx-auto grid h-full max-w-[1400px] grid-cols-2 gap-12 px-6 pt-[60vh] md:gap-40 md:px-10">
          {columns.map((col, c) => (
            <div key={c} ref={c === 0 ? left : right} className={cn('flex flex-col gap-[40vh]', c === 0 ? 'items-start' : 'items-end')}>
              {col.map((item) => (
                <SignalCard key={item.title} item={item} onOpen={() => setOpen(item)} />
              ))}
            </div>
          ))}
        </div>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 p-6 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setOpen(null)}
            role="dialog"
            aria-modal="true"
            aria-label={open.title}
          >
            <motion.div
              initial={{ scale: 0.92, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="relative w-full max-w-lg rounded-3xl border border-stroke bg-surface p-8"
            >
              <button onClick={() => setOpen(null)} className="absolute right-4 top-4 rounded-full p-2 text-muted hover:text-text-primary" aria-label="Close">
                <X className="h-4 w-4" />
              </button>
              <p className={cn('text-sm font-medium', TONE[open.tone])}>{open.kicker}</p>
              <p className="mt-3 font-display text-4xl italic text-text-primary">{open.title}</p>
              <p className="mt-2 text-xs uppercase tracking-[0.15em] text-muted">{open.meta}</p>
              <p className="mt-6 text-sm leading-relaxed text-text-primary/85">{open.detail}</p>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
