import { ArrowDown, ArrowRight } from 'lucide-react';
import { motion } from 'motion/react';

import { EASE, SectionHeader } from '@/components/landing/SectionHeader';
import { Badge } from '@/components/ui';
import { cn } from '@/lib/format';
import { MODALITIES } from '@/lib/modules';

const STEPS = [
  { title: 'Input', body: 'Hashed with SHA-256 and stored unmodified.' },
  { title: 'AI analysis', body: 'Engines extract entities, claims, features and signals.' },
  { title: 'Evidence', body: 'Claims checked against retrieved, ranked sources.' },
  { title: 'Risk assessment', body: 'Configurable weights; every point attributed.' },
  { title: 'Explainable result', body: 'Signals, provenance, uncertainty and next steps.' },
];

export function Pipeline() {
  return (
    <section id="pipeline" className="bg-bg py-16 md:py-24">
      <div className="mx-auto max-w-[1200px] px-6 md:px-10 lg:px-16">
        <SectionHeader
          eyebrow="How it works"
          title={<>One pipeline, <span className="font-display italic">every</span> input</>}
          subtext="Nothing is sent to a language model and relayed as a verdict. Each stage is a separate, audited step — and the timeline records the ones that were skipped, and why."
        />

        <ol className="grid gap-3 md:grid-cols-5 md:gap-4">
          {STEPS.map((step, i) => (
            <motion.li
              key={step.title}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-80px' }}
              transition={{ duration: 0.8, delay: i * 0.08, ease: EASE }}
              className="relative rounded-3xl border border-stroke bg-surface/40 p-5"
            >
              <span className="text-xs tabular-nums text-muted">0{i + 1}</span>
              <p className="mt-3 font-display text-2xl italic text-text-primary">{step.title}</p>
              <p className="mt-2 text-sm text-muted">{step.body}</p>
              {i < STEPS.length - 1 && (
                <>
                  <ArrowRight className="absolute -right-3 top-1/2 z-10 hidden h-4 w-4 -translate-y-1/2 text-muted md:block" aria-hidden />
                  <ArrowDown className="absolute -bottom-3 left-1/2 z-10 h-4 w-4 -translate-x-1/2 text-muted md:hidden" aria-hidden />
                </>
              )}
            </motion.li>
          ))}
        </ol>

        <div className="mt-12">
          <p className="mb-4 text-xs uppercase tracking-[0.3em] text-muted">Inputs</p>
          <div className="flex flex-wrap gap-3">
            {MODALITIES.map((m, i) => (
              <motion.div
                key={m.label}
                initial={{ opacity: 0, scale: 0.9 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.05, ease: EASE }}
                className={cn(
                  'flex items-center gap-3 rounded-full border px-5 py-3',
                  m.availability === 'live' ? 'border-stroke bg-surface' : 'border-dashed border-stroke bg-transparent',
                )}
              >
                <span className={cn('text-sm font-medium tracking-wide', m.availability === 'live' ? 'text-text-primary' : 'text-muted')}>
                  {m.label.toUpperCase()}
                </span>
                {m.availability === 'live' ? (
                  <Badge tone="good">Live</Badge>
                ) : (
                  <Badge>Phase {m.phase}</Badge>
                )}
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
