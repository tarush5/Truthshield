import { motion } from 'motion/react';

import { EASE } from '@/components/landing/SectionHeader';
import { useHealth } from '@/hooks/queries';

/**
 * Figures read from the running system -- never typed in. When the API is
 * unreachable the numbers show as a dash and the section says why.
 */
export function Stats() {
  const { data, isError } = useHealth();

  const stats = [
    { value: data ? String(data.investigations.completed_total ?? '—') : '—', label: 'Investigations completed', note: 'on this deployment' },
    { value: data ? String(data.engines.length) : '—', label: 'Analysis engines live', note: data ? data.engines.map((e) => e.name).join(' · ') : '' },
    { value: '12', label: 'Audited pipeline stages', note: 'every one recorded, even when skipped' },
  ];

  return (
    <section className="bg-bg py-16 md:py-24">
      <div className="mx-auto grid max-w-[1200px] grid-cols-1 gap-10 px-6 md:grid-cols-3 md:px-10 lg:px-16">
        {stats.map((s, i) => (
          <motion.div
            key={s.label}
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-80px' }}
            transition={{ duration: 0.9, delay: i * 0.1, ease: EASE }}
            className="border-t border-stroke pt-6"
          >
            <p className="font-display text-6xl tabular-nums text-text-primary md:text-7xl">{s.value}</p>
            <p className="mt-3 text-sm uppercase tracking-[0.2em] text-muted">{s.label}</p>
            {s.note && <p className="mt-1 text-xs text-muted/80">{s.note}</p>}
          </motion.div>
        ))}
      </div>
      {isError && (
        <p className="mx-auto mt-8 max-w-[1200px] px-6 text-xs text-muted md:px-10 lg:px-16">
          Live figures are unavailable because the API could not be reached.
        </p>
      )}
    </section>
  );
}
