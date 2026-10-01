import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { LazyMotion, MotionGlobalConfig } from 'motion/react';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import App from '@/App';
import { ApiError } from '@/lib/api';
import { SKIP_MOTION } from '@/lib/env';
import './index.css';

if (SKIP_MOTION) MotionGlobalConfig.skipAnimations = true;

const loadMotionFeatures = () => import('@/lib/motion-features').then((mod) => mod.default);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: false,
      // Retrying a 4xx never helps; a transient network or 5xx error might.
      retry: (count, error) => !(error instanceof ApiError && error.status >= 400 && error.status < 500) && count < 2,
    },
  },
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      {/* `strict` makes a stray full-size <motion.*> component throw in dev. */}
      <LazyMotion features={loadMotionFeatures} strict>
        <App />
      </LazyMotion>
    </QueryClientProvider>
  </StrictMode>,
);
