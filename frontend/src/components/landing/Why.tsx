import { ArrowLeft, ArrowRight, Bot, Gauge, Layers, Sigma } from 'lucide-react';
import { AnimatePresence, m } from 'motion/react';
import { useState } from 'react';

import { BreakdownCard } from '@/components/landing/CaseCards';
import { CASES } from '@/components/landing/cases';
import { PALETTE, pad, type Colour } from '@/components/landing/palette';
import { cn } from '@/lib/format';

/**
 * Four design facts, not measurements: each is how the system is built and
 * can be checked in the code or in any result.
 */
const REASONS: { stat: string; label: string; instead: string; body: string; icon: typeof Bot; colour: Colour; caseId: string }[] = [
  {
    stat: '12',
    label: 'recorded stages',
    instead: 'a black box',
    body: 'Every investigation leaves a timeline you can audit, stage by stage, with what was skipped and why.',
    icon: Layers,
    colour: 'orange',
    caseId: 'phishing-sms',
  },
  {
    stat: '0',
    label: 'verdicts decided by an LLM',
    instead: "a chatbot's opinion",
    body: 'Rules, retrieval and deterministic checks decide. A language model may explain the findings; it never changes them.',
    icon: Bot,
    colour: 'blue',
    caseId: 'prompt-injection',
  },
  {
    stat: '99',
    label: 'is the highest score',
    instead: '100% certain',
    body: 'No combination of signals is proof, so the scale stops short of 100. Confidence is reported separately.',
    icon: Gauge,
    colour: 'green',
    caseId: 'phishing-email',
  },
  {
    stat: '100%',
    label: 'of points explained',
    instead: 'scam: 95%',
    body: 'The breakdown adds up exactly to the score, and each signal shows the evidence it was based on.',
    icon: Sigma,
    colour: 'amber',
    caseId: 'suspicious-url',
  },
];

export function Why() {
  const [i, setI] = useState(0);
  const n = REASONS.length;
  const r = REASONS[i];
  const p = PALETTE[r.colour];
  const c = CASES.find((x) => x.id === r.caseId) ?? CASES[0];

  return (
    <section id="why" aria-label="Why TruthShield" className="grid min-h-[100svh] lg:grid-cols-2">
      <div className="relative flex min-h-[420px] items-center justify-center overflow-hidden transition-colors duration-500" style={{ background: p.bg }}>
        <div aria-hidden className="absolute h-[60%] w-[60%] rounded-full transition-colors duration-500" style={{ background: p.soft, opacity: 0.45 }} />
        <AnimatePresence mode="wait">
          <m.div
            key={r.caseId}
            initial={{ opacity: 0, rotate: 12, y: 40 }}
            animate={{ opacity: 1, rotate: 5, y: 0 }}
            exit={{ opacity: 0, rotate: -6, y: -30 }}
            transition={{ type: 'spring', stiffness: 130, damping: 18 }}
          >
            <BreakdownCard c={c} />
          </m.div>
        </AnimatePresence>
      </div>

      <div className="flex flex-col justify-center bg-bg px-6 py-20 sm:px-12 lg:px-16">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-muted">
          Why TruthShield · {pad(i + 1)} / {pad(n)}
        </p>
        <AnimatePresence mode="wait">
          <m.div key={i} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }} transition={{ duration: 0.3 }}>
            <p className="font-display mt-4 text-[clamp(96px,13vw,190px)] leading-[0.8] tabular">{r.stat}</p>
            <p className="font-display mt-3 text-3xl leading-tight sm:text-4xl">{r.label}</p>
            <p className="mt-5 flex flex-wrap items-center gap-2 text-sm text-muted">
              instead of
              <span className="rounded-full bg-stroke/70 px-3 py-1 font-semibold text-text-primary line-through decoration-2">{r.instead}</span>
            </p>
            <p className="mt-5 max-w-md text-lg font-medium leading-snug">{r.body}</p>
          </m.div>
        </AnimatePresence>

        <div className="mt-10 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => setI((i - 1 + n) % n)}
            aria-label="Previous reason"
            className="flex h-12 w-12 items-center justify-center rounded-full border-2 border-text-primary transition-colors hover:bg-text-primary hover:text-bg"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => setI((i + 1) % n)}
            aria-label="Next reason"
            className="flex h-12 w-12 items-center justify-center rounded-full border-2 border-text-primary transition-colors hover:bg-text-primary hover:text-bg"
          >
            <ArrowRight className="h-4 w-4" />
          </button>
          <span className="mx-1 h-8 w-px bg-stroke" aria-hidden />
          <div className="flex gap-2" role="tablist" aria-label="Reasons">
            {REASONS.map((reason, k) => {
              const Icon = reason.icon;
              const on = k === i;
              return (
                <button
                  key={reason.label}
                  type="button"
                  role="tab"
                  aria-selected={on}
                  aria-label={`${reason.stat} ${reason.label}`}
                  onClick={() => setI(k)}
                  className={cn('flex h-12 w-12 items-center justify-center rounded-full transition-colors', on ? 'text-[#FFF6EA]' : 'bg-stroke/60 text-text-primary hover:bg-stroke')}
                  style={on ? { background: PALETTE[reason.colour].bg, color: PALETTE[reason.colour].ink } : undefined}
                >
                  <Icon className="h-5 w-5" />
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
