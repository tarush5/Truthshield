import { motion } from 'motion/react';
import type { ReactNode } from 'react';

import { Eyebrow } from '@/components/ui';

export const EASE = [0.25, 0.1, 0.25, 1] as const;

export function SectionHeader({ eyebrow, title, subtext, action, center = false }: {
  eyebrow: string;
  title: ReactNode;
  subtext: string;
  action?: ReactNode;
  center?: boolean;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-100px' }}
      transition={{ duration: 1, ease: EASE }}
      className={center ? 'mb-12 flex flex-col items-center text-center md:mb-16' : 'mb-12 flex flex-col gap-6 md:mb-16 md:flex-row md:items-end md:justify-between'}
    >
      <div className={center ? 'flex flex-col items-center' : ''}>
        <Eyebrow className="mb-6">{eyebrow}</Eyebrow>
        <h2 className="text-4xl font-medium tracking-tight text-text-primary md:text-6xl">{title}</h2>
        <p className="mt-4 max-w-lg text-sm text-muted md:text-base">{subtext}</p>
      </div>
      {action && <div className="hidden md:inline-flex">{action}</div>}
    </motion.div>
  );
}
