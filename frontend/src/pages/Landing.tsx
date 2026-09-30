import { AnimatePresence } from 'motion/react';
import { useCallback, useEffect, useState } from 'react';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

import { Capabilities } from '@/components/landing/Capabilities';
import { Contact } from '@/components/landing/Contact';
import { Explainability } from '@/components/landing/Explainability';
import { Hero } from '@/components/landing/Hero';
import { LoadingScreen } from '@/components/landing/LoadingScreen';
import { Navbar } from '@/components/landing/Navbar';
import { Pipeline } from '@/components/landing/Pipeline';
import { Principles } from '@/components/landing/Principles';
import { Stats } from '@/components/landing/Stats';
import { SKIP_MOTION } from '@/lib/env';

// Once per tab session: the intro is a welcome, not a toll on every visit.
let introShown = SKIP_MOTION;

export default function Landing() {
  const [loading, setLoading] = useState(!introShown);

  const finish = useCallback(() => {
    introShown = true;
    setLoading(false);
  }, []);

  useEffect(() => {
    document.body.style.overflow = loading ? 'hidden' : '';
    if (!loading) {
      // Scroll locking changed the layout; pinned sections need fresh offsets.
      requestAnimationFrame(() => ScrollTrigger.refresh());
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [loading]);

  return (
    <>
      <AnimatePresence>{loading && <LoadingScreen onComplete={finish} />}</AnimatePresence>
      <Navbar />
      <main>
        <Hero ready={!loading} />
        <Pipeline />
        <Capabilities />
        <Principles />
        <Explainability />
        <Stats />
      </main>
      <Contact />
    </>
  );
}
