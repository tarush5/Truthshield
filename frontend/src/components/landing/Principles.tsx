import { motion } from 'motion/react';

import { EASE, SectionHeader } from '@/components/landing/SectionHeader';

const img = (id: string) => `https://images.unsplash.com/photo-${id}?auto=format&fit=crop&w=300&q=60`;

const PRINCIPLES = [
  {
    title: 'Evidence over assertion',
    body: 'Every signal quotes the exact excerpt that triggered it.',
    tag: 'Provenance',
    where: 'Signals tab',
    image: img('1507842217343-583bb7270b66'),
  },
  {
    title: 'Uncertainty is an output',
    body: 'What could not be checked is listed, never implied clean.',
    tag: 'Uncertainty',
    where: 'Overview',
    image: img('1541701494587-cb58502866ab'),
  },
  {
    title: 'Every point is attributable',
    body: 'The risk breakdown sums exactly to the score.',
    tag: 'Risk engine',
    where: 'Risk breakdown',
    image: img('1551288049-bebda4e38f71'),
  },
  {
    title: 'Untrusted input stays data',
    body: 'Instructions hidden in content are flagged, not obeyed.',
    tag: 'Security',
    where: 'Signals tab',
    image: img('1550751827-4bd374c3f58b'),
  },
];

export function Principles() {
  return (
    <section className="bg-bg py-16 md:py-24">
      <div className="mx-auto max-w-[1200px] px-6 md:px-10 lg:px-16">
        <SectionHeader
          eyebrow="Principles"
          title={<>How we <span className="font-display italic">decide</span></>}
          subtext="Four rules every investigation follows. Each one is visible in the result, not just stated here."
        />
        <ul className="flex flex-col gap-4">
          {PRINCIPLES.map((p, i) => (
            <motion.li
              key={p.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{ duration: 0.8, delay: i * 0.06, ease: EASE }}
              className="flex items-center gap-6 rounded-[40px] border border-stroke bg-surface/30 p-4 transition-colors hover:bg-surface sm:rounded-full"
            >
              <img src={p.image} alt="" loading="lazy" className="h-16 w-16 shrink-0 rounded-full object-cover sm:h-20 sm:w-20" />
              <div className="min-w-0 flex-1">
                <p className="text-base font-medium text-text-primary sm:text-lg">{p.title}</p>
                <p className="mt-1 text-sm text-muted">{p.body}</p>
              </div>
              <div className="hidden shrink-0 flex-col items-end gap-1 pr-4 text-right sm:flex">
                <span className="text-xs uppercase tracking-[0.2em] text-muted">{p.tag}</span>
                <span className="text-sm text-text-primary/80">See: {p.where}</span>
              </div>
            </motion.li>
          ))}
        </ul>
      </div>
    </section>
  );
}
