import { AnimatePresence, motion } from 'motion/react';
import { Suspense, lazy, type ReactNode } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useLocation, useOutlet } from 'react-router-dom';

import { Spinner } from '@/components/ui';
import { SKIP_MOTION } from '@/lib/env';
import { useAuth } from '@/stores/auth';

// The shell is only needed once signed in, so landing visitors never download it.
const AppShell = lazy(() => import('@/components/shell/AppShell').then((m) => ({ default: m.AppShell })));
const Landing = lazy(() => import('@/pages/Landing'));
const Login = lazy(() => import('@/pages/Login'));
const Dashboard = lazy(() => import('@/pages/Dashboard'));
const Investigate = lazy(() => import('@/pages/Investigate'));
const InvestigationResult = lazy(() => import('@/pages/InvestigationResult'));
const History = lazy(() => import('@/pages/History'));
const UrlIntelligence = lazy(() => import('@/pages/UrlIntelligence'));
const Settings = lazy(() => import('@/pages/Settings'));
const ModulePage = lazy(() => import('@/pages/ModulePage'));
const LegacyReport = lazy(() => import('@/pages/LegacyReport'));

function Fallback() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <Spinner className="h-6 w-6" />
    </div>
  );
}

/**
 * Page transitions animate opacity only. A transform or filter on the
 * wrapper would become the containing block for every `position: fixed`
 * descendant -- the navbar, dialogs and GSAP's pinned sections would break.
 */
const fade = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 },
  transition: { duration: 0.25, ease: 'easeOut' as const },
};

function Page({ children }: { children: ReactNode }) {
  if (SKIP_MOTION) return <Suspense fallback={<Fallback />}>{children}</Suspense>;
  return (
    <motion.div {...fade}>
      <Suspense fallback={<Fallback />}>{children}</Suspense>
    </motion.div>
  );
}

/** Inside the shell, only the content cross-fades; the sidebar stays put. */
function AnimatedOutlet() {
  const location = useLocation();
  const outlet = useOutlet();
  if (SKIP_MOTION) return <Suspense fallback={<Fallback />}>{outlet}</Suspense>;
  return (
    <AnimatePresence mode="wait" onExitComplete={() => window.scrollTo(0, 0)}>
      <motion.div key={location.pathname} {...fade}>
        <Suspense fallback={<Fallback />}>{outlet}</Suspense>
      </motion.div>
    </AnimatePresence>
  );
}

function ProtectedShell() {
  const signedIn = useAuth((s) => Boolean(s.accessToken));
  const location = useLocation();
  if (!signedIn) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return (
    <Suspense fallback={<Fallback />}>
      <AppShell>
        <AnimatedOutlet />
      </AppShell>
    </Suspense>
  );
}

function AnimatedRoutes() {
  const location = useLocation();
  // Top-level transitions happen between areas (landing, login, app), not
  // between pages inside the app.
  const area = location.pathname.startsWith('/app') || location.pathname.startsWith('/report') ? 'app' : location.pathname;

  const routes = (
      <Routes location={location} key={area}>
        <Route path="/" element={<Page><Landing /></Page>} />
        <Route path="/login" element={<Page><Login /></Page>} />
        <Route path="/shared/:token" element={<Page><LegacyReport shared /></Page>} />

        <Route element={<ProtectedShell />}>
          <Route path="/app" element={<Dashboard />} />
          <Route path="/app/investigate" element={<Investigate />} />
          <Route path="/app/investigations/:id" element={<InvestigationResult />} />
          <Route path="/app/history" element={<History />} />
          <Route path="/app/url-intelligence" element={<UrlIntelligence />} />
          <Route path="/app/settings" element={<Settings />} />
          <Route path="/app/m/:module" element={<ModulePage />} />
          {/* 1.x report links keep working. */}
          <Route path="/report/:id" element={<LegacyReport />} />
        </Route>

        <Route path="/analyze" element={<Navigate to="/app/investigate" replace />} />
        <Route path="/history" element={<Navigate to="/app/history" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
  );
  if (SKIP_MOTION) return routes;
  return (
    <AnimatePresence mode="wait" onExitComplete={() => window.scrollTo(0, 0)}>
      {routes}
    </AnimatePresence>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AnimatedRoutes />
    </BrowserRouter>
  );
}
