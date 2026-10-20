/**
 * Everything on the landing page below the hero, as its own chunk.
 *
 * The hero is what a visitor sees first; these sections, and GSAP's
 * ScrollTrigger that the parallax needs, download in parallel instead of
 * delaying it. Landing starts the import as soon as its own module runs.
 */
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useEffect } from 'react';

import { Capabilities } from '@/components/landing/Capabilities';
import { Contact } from '@/components/landing/Contact';
import { Explainability } from '@/components/landing/Explainability';
import { Pipeline } from '@/components/landing/Pipeline';
import { Principles } from '@/components/landing/Principles';
import { Stats } from '@/components/landing/Stats';

export default function BelowFold({ ready }: { ready: boolean }) {
  useEffect(() => {
    if (!ready) return;
    // The intro's scroll lock, and these sections arriving after the hero,
    // both change the layout: pinned sections need fresh offsets.
    const frame = requestAnimationFrame(() => ScrollTrigger.refresh());
    return () => cancelAnimationFrame(frame);
  }, [ready]);

  return (
    <>
      <Pipeline />
      <Capabilities />
      <Principles />
      <Explainability />
      <Stats />
    </>
  );
}

export function Footer() {
  return <Contact />;
}
