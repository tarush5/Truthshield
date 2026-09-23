import React, { Suspense, lazy, useEffect, useState } from 'react';
import {
  BrowserRouter as Router, Link, Navigate, Route, Routes, useLocation,
} from 'react-router-dom';
import { Moon, ShieldCheck, Sun } from 'lucide-react';

import CommandPalette from './components/CommandPalette';
import AppShell from './components/shell/AppShell';
import { SkeletonCard, ToastProvider } from './components/ui';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Landing from './pages/Landing';

// Everything behind auth is split out, so a signed-out visitor does not
// download the report and history code to read the landing page.
const Analyze = lazy(() => import('./pages/Analyze'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const History = lazy(() => import('./pages/History'));
const Login = lazy(() => import('./pages/Login'));
const Report = lazy(() => import('./pages/Report'));
const SharedReport = lazy(() => import('./pages/SharedReport'));

/**
 * A route that is still arriving.
 *
 * Skeletons in the shape of the page rather than a spinner: the layout is
 * already known, so reserving it stops the content jumping into place when
 * the chunk lands.
 */
function RouteFallback() {
  return (
    <div className="mx-auto max-w-5xl px-5 sm:px-8">
      <div className="mb-7 space-y-3">
        <div className="skeleton h-8 w-48" />
        <div className="skeleton h-4 w-72" />
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
      </div>
    </div>
  );
}

function useTheme() {
  const [theme, setTheme] = useState(() => {
    try { return localStorage.getItem('theme') || 'dark'; } catch { return 'dark'; }
  });

  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove('dark', 'light');
    root.classList.add(theme);
    try { localStorage.setItem('theme', theme); } catch { /* private mode */ }
  }, [theme]);

  return [theme, () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))];
}

/**
 * The header for pages nobody is signed in to.
 *
 * Separate from the application shell on purpose: a navigation rail listing
 * destinations a visitor cannot open is worse than no rail, and a shared
 * report needs to read as a document rather than as somebody's dashboard.
 */
function PublicHeader({ theme, onToggleTheme }) {
  const { isAuthenticated } = useAuth();

  return (
    <header
      className="sticky top-0 border-b border-line bg-page/85 backdrop-blur-md"
      style={{ zIndex: 'var(--z-nav)' }}
    >
      <nav className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-5 sm:px-8">
        <Link to="/" className="focusable flex shrink-0 items-center gap-2.5 rounded-lg">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand shadow-sm">
            <ShieldCheck className="h-4 w-4 text-white" aria-hidden="true" />
          </span>
          <span className="text-[0.9375rem] font-bold tracking-tight text-ink">TruthShield</span>
        </Link>

        <div className="flex items-center gap-1.5">
          <button
            onClick={onToggleTheme}
            className="btn-ghost !p-2"
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
          >
            {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
          <Link to={isAuthenticated ? '/analyze' : '/login'} className="btn-primary !px-4 !py-1.5 text-sm">
            {isAuthenticated ? 'Open app' : 'Sign in'}
          </Link>
        </div>
      </nav>
    </header>
  );
}

function PublicLayout({ theme, onToggleTheme, wash = false, children }) {
  return (
    <div className="relative min-h-screen bg-page">
      <div className="page-wash pointer-events-none fixed inset-0" aria-hidden="true" />
      {wash && <div className="grid-wash pointer-events-none fixed inset-0" aria-hidden="true" />}

      <div className="relative flex min-h-screen flex-col" style={{ zIndex: 1 }}>
        <PublicHeader theme={theme} onToggleTheme={onToggleTheme} />
        <main className="flex-1">{children}</main>
        <footer className="border-t border-line py-6">
          <div className="mx-auto max-w-6xl px-5 text-[0.6875rem] text-ink-muted sm:px-8">
            Verdicts are automated and can be wrong. Check the sources before relying on one.
          </div>
        </footer>
      </div>
    </div>
  );
}

function Protected({ children }) {
  const { isAuthenticated, checking } = useAuth();
  const location = useLocation();

  // Wait for the session check before redirecting; otherwise a reload on a
  // protected page bounces to sign-in for a frame and back again.
  if (checking) return <RouteFallback />;
  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: location }} />;
  return children;
}

function HomeRoute({ theme, onToggleTheme }) {
  const { isAuthenticated, checking } = useAuth();
  if (checking) return null;
  if (isAuthenticated) return <Navigate to="/analyze" replace />;
  return (
    <PublicLayout theme={theme} onToggleTheme={onToggleTheme} wash>
      <Landing />
    </PublicLayout>
  );
}

function Shell() {
  const { pathname } = useLocation();
  const { isAuthenticated } = useAuth();
  const [theme, toggleTheme] = useTheme();
  const [paletteOpen, setPaletteOpen] = useState(false);

  // ⌘K / Ctrl+K anywhere. Bound on the window rather than an element so it
  // works regardless of what has focus.
  useEffect(() => {
    if (!isAuthenticated) return undefined;
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isAuthenticated]);

  // Close on navigation, so a back gesture never leaves it stranded open.
  useEffect(() => { setPaletteOpen(false); }, [pathname]);

  // A route change should start at the top. Without this, opening a report
  // from halfway down the history list lands mid-page.
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);

  const publicShell = (element, wash = false) => (
    <PublicLayout theme={theme} onToggleTheme={toggleTheme} wash={wash}>
      {element}
    </PublicLayout>
  );

  const appShell = (element) => (
    <AppShell theme={theme} onToggleTheme={toggleTheme} onOpenPalette={() => setPaletteOpen(true)}>
      <Protected>{element}</Protected>
    </AppShell>
  );

  return (
    <>
      <Suspense fallback={<RouteFallback />}>
        <Routes>
          <Route path="/" element={<HomeRoute theme={theme} onToggleTheme={toggleTheme} />} />
          <Route path="/login" element={publicShell(<Login />)} />
          {/* Public by design: the whole point of a share link is that the
              recipient does not have an account. */}
          <Route path="/shared/:token" element={publicShell(<SharedReport />)} />

          <Route path="/analyze" element={appShell(<Analyze />)} />
          <Route path="/report/:id" element={appShell(<Report />)} />
          <Route path="/history" element={appShell(<History />)} />
          <Route path="/insights" element={appShell(<Dashboard />)} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>

      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onToggleTheme={toggleTheme}
        theme={theme}
      />
    </>
  );
}

export default function App() {
  return (
    <Router>
      <AuthProvider>
        <ToastProvider>
          <Shell />
        </ToastProvider>
      </AuthProvider>
    </Router>
  );
}
