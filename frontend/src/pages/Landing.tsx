import { Suspense, lazy } from 'react';

import { Hero } from '@/components/landing/Hero';
import { Navbar } from '@/components/landing/Navbar';

// Below the fold is its own chunk, requested the moment this module runs so
// it downloads alongside the hero rather than after it.
const loadBelowFold = () => import('@/components/landing/BelowFold');
void loadBelowFold();
const BelowFold = lazy(loadBelowFold);
const Footer = lazy(() => loadBelowFold().then((m) => ({ default: m.Footer })));

export default function Landing() {
  return (
    <div className="bg-bg font-body text-text-primary">
      <Navbar />
      <main>
        <Hero />
        <Suspense fallback={null}>
          <BelowFold />
        </Suspense>
      </main>
      <Suspense fallback={null}>
        <Footer />
      </Suspense>
    </div>
  );
}
