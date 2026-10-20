import { AnimatePresence } from 'motion/react';
import { Suspense, lazy, useCallback, useEffect, useState } from 'react';

import { Hero } from '@/components/landing/Hero';
import { LoadingScreen } from '@/components/landing/LoadingScreen';
import { Navbar } from '@/components/landing/Navbar';
import { SKIP_MOTION } from '@/lib/env';

// Below the fold is its own chunk, requested the moment this module runs so
// it downloads alongside the hero rather than after it.
const loadBelowFold = () => import('@/components/landing/BelowFold');
void loadBelowFold();
const BelowFold = lazy(loadBelowFold);
const Footer = lazy(() => loadBelowFold().then((m) => ({ default: m.Footer })));

// Once per tab session (surviving reloads): the intro is a welcome, not a
// toll on every visit. Storage can throw in private modes; then it shows once
// per page load.
const INTRO_KEY = 'ts.introShown';
let introShown = SKIP_MOTION || readIntro();

function readIntro() {
  try {
    return sessionStorage.getItem(INTRO_KEY) === '1';
  } catch {
    return false;
  }
}

export default function Landing() {
  const [loading, setLoading] = useState(!introShown);

  const finish = useCallback(() => {
    introShown = true;
    try {
      sessionStorage.setItem(INTRO_KEY, '1');
    } catch {
      /* not persisted; harmless */
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    document.body.style.overflow = loading ? 'hidden' : '';
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
        <Suspense fallback={null}>
          <BelowFold ready={!loading} />
        </Suspense>
      </main>
      <Suspense fallback={null}>
        <Footer />
      </Suspense>
    </>
  );
}
