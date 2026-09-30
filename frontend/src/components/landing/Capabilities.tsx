import { ArrowRight } from 'lucide-react';
import { motion } from 'motion/react';
import { Link } from 'react-router-dom';

import { EASE, SectionHeader } from '@/components/landing/SectionHeader';
import { Badge, ButtonLink } from '@/components/ui';
import { cn } from '@/lib/format';
import { AVAILABILITY_LABEL, CAPABILITIES } from '@/lib/modules';
import { useAuth } from '@/stores/auth';

// Alternating 7/5, 5/7 rhythm; the last card closes the grid full-width.
const SPANS = ['md:col-span-7', 'md:col-span-5', 'md:col-span-5', 'md:col-span-7', 'md:col-span-7', 'md:col-span-5', 'md:col-span-5', 'md:col-span-7', 'md:col-span-12'];
const RATIOS = ['aspect-[4/3] md:aspect-[16/11]', 'aspect-[4/3] md:aspect-[5/6]', 'aspect-[4/3] md:aspect-[5/6]', 'aspect-[4/3] md:aspect-[16/11]'];

export function Capabilities() {
  const signedIn = useAuth((s) => Boolean(s.accessToken));

  return (
    <section id="capabilities" className="bg-bg py-12 md:py-16">
      <div className="mx-auto max-w-[1200px] px-6 md:px-10 lg:px-16">
        <SectionHeader
          eyebrow="Capabilities"
          title={<>Built for <span className="font-display italic">investigators</span></>}
          subtext="What is live today and what is still being built — labelled plainly, because a trust platform that overstates itself has already failed."
          action={
            <ButtonLink to={signedIn ? '/app' : '/login'} variant="outline" size="sm">
              Open the platform <ArrowRight className="h-4 w-4" aria-hidden />
            </ButtonLink>
          }
        />

        <div className="grid grid-cols-1 gap-5 md:grid-cols-12 md:gap-6">
          {CAPABILITIES.map((cap, i) => (
            <motion.div
              key={cap.id}
              className={SPANS[i]}
              initial={{ opacity: 0, y: 40 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-80px' }}
              transition={{ duration: 0.9, delay: (i % 2) * 0.1, ease: EASE }}
            >
              <Link
                to={signedIn ? cap.route : '/login'}
                className={cn(
                  'group relative block overflow-hidden rounded-3xl border border-stroke bg-surface',
                  i === CAPABILITIES.length - 1 ? 'aspect-[4/3] md:aspect-[21/8]' : RATIOS[i % 4],
                )}
              >
                <img
                  src={cap.image}
                  alt=""
                  loading="lazy"
                  className="absolute inset-0 h-full w-full object-cover transition-transform duration-700 group-hover:scale-105"
                />
                <div className="halftone absolute inset-0 opacity-20 mix-blend-multiply" aria-hidden />
                <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/30 to-transparent" aria-hidden />

                <div className="absolute inset-x-0 bottom-0 p-5 md:p-7">
                  <Badge tone={cap.availability === 'live' ? 'good' : cap.availability === 'partial' ? 'accent' : 'neutral'} className="mb-3 backdrop-blur-md">
                    {AVAILABILITY_LABEL[cap.availability]}
                    {cap.availability !== 'live' && ` · Phase ${cap.phase}`}
                  </Badge>
                  <h3 className="text-2xl font-medium text-white md:text-3xl">{cap.title}</h3>
                  <p className="mt-2 max-w-md text-sm text-white/70">{cap.summary}</p>
                </div>

                {/* Hover: blur overlay and the gradient-ringed label. */}
                <div className="absolute inset-0 flex items-center justify-center bg-bg/70 opacity-0 backdrop-blur-lg transition-opacity duration-500 group-hover:opacity-100 group-focus-visible:opacity-100">
                  <span className="accent-gradient-animated rounded-full p-[2px]">
                    <span className="flex items-center gap-2 rounded-full bg-white px-5 py-2.5 text-sm text-black">
                      Explore — <span className="font-display text-base italic">{cap.title}</span>
                    </span>
                  </span>
                </div>
              </Link>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
