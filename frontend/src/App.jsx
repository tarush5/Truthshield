import React, { Suspense, lazy, useEffect, useState } from 'react';
import {
  BrowserRouter as Router, Link, Navigate, Route, Routes, useLocation,
} from 'react-router-dom';
import { Command, Loader2, LogOut, Moon, ShieldCheck, Sun } from 'lucide-react';

import CommandPalette from './components/CommandPalette';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Landing from './pages/Landing';

// Everything behind auth is split out, so a signed-out visitor does not
// download the report and history code to read the landing page.
const Analyze = lazy(() => import('./pages/Analyze'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const SharedReport = lazy(() => import('./pages/SharedReport'));
const Report = lazy(() => import('./pages/Report'));
const History = lazy(() => import('./pages/History'));
const Login = lazy(() => import('./pages/Login'));

function Fallback() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <Loader2 className="h-5 w-5 animate-spin text-brand" />
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

function NavBar({ theme, toggleTheme, onOpenPalette }) {
  const { user, signOut } = useAuth();
  const { pathname } = useLocation();

  const links = user
    ? [
        { to: '/analyze', label: 'Check' },
        { to: '/history', label: 'History' },
        { to: '/insights', label: 'Insights' },
      ]
    : [];

  return (
    <header className="sticky top-0 z-50 border-b border-line bg-page/85 backdrop-blur-md">
      <nav className="mx-auto flex h-14 max-w-5xl items-center justify-between gap-4 px-5 sm:px-8">
        <Link
          to={user ? '/analyze' : '/'}
          className="flex shrink-0 items-center gap-2.5 rounded-lg"
        >
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand">
            <ShieldCheck className="h-4 w-4 text-white" />
          </span>
          <span className="text-[0.9375rem] font-bold tracking-tight text-ink">
            TruthShield
          </span>
        </Link>

        <div className="flex items-center gap-1">
          {links.map(({ to, label }) => (
            <Link
              key={to}
              to={to}
              aria-current={pathname === to ? 'page' : undefined}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                pathname === to
                  ? 'bg-brand/12 text-brand'
                  : 'text-ink-muted hover:bg-line/[0.06] hover:text-ink'
              }`}
            >
              {label}
            </Link>
          ))}

          {user && (
            <button
              onClick={onOpenPalette}
              className="mr-1 hidden items-center gap-2 rounded-lg border border-line px-2.5 py-1.5 text-2xs text-ink-muted transition-colors hover:text-ink sm:inline-flex"
              aria-label="Open command palette"
            >
              <Command className="h-3 w-3" />
              <span className="font-mono">K</span>
            </button>
          )}

          <button
            onClick={toggleTheme}
            className="btn-ghost !p-2"
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
          >
            {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>

          {user ? (
            <button onClick={signOut} className="btn-ghost !p-2" aria-label="Sign out">
              <LogOut className="h-4 w-4" />
            </button>
          ) : (
            <Link to="/login" className="btn-primary !px-4 !py-1.5 text-sm">
              Sign in
            </Link>
          )}
        </div>
      </nav>
    </header>
  );
}

function Protected({ children }) {
  const { isAuthenticated, checking } = useAuth();
  const location = useLocation();

  // Wait for the session check before redirecting; otherwise a reload on a
  // protected page bounces to sign-in for a frame and back again.
  if (checking) return <Fallback />;
  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: location }} />;
  return children;
}

function HomeRoute() {
  const { isAuthenticated, checking } = useAuth();
  if (checking) return <Fallback />;
  return isAuthenticated ? <Navigate to="/analyze" replace /> : <Landing />;
}

function Shell() {
  const { pathname } = useLocation();
  const { isAuthenticated } = useAuth();
  const [theme, toggleTheme] = useTheme();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const isLanding = pathname === '/';

  // ⌘K / Ctrl+K anywhere. Bound on the window rather than a element so it
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

  return (
    <div className="relative min-h-screen bg-page">
      {/* Ambient wash. Fixed and non-interactive; the grid only joins it on
          the landing page, where there is enough empty space to carry it. */}
      <div className="page-wash pointer-events-none fixed inset-0" aria-hidden="true" />
      {isLanding && (
        <div className="grid-wash pointer-events-none fixed inset-0" aria-hidden="true" />
      )}

      <div className="relative z-10 flex min-h-screen flex-col">
        <NavBar theme={theme} toggleTheme={toggleTheme} onOpenPalette={() => setPaletteOpen(true)} />
        <main className="flex-1 py-10 sm:py-14">
          <Suspense fallback={<Fallback />}>
            <Routes>
              <Route path="/" element={<HomeRoute />} />
              <Route path="/login" element={<Login />} />
              {/* Public by design: the whole point of a share link is
                  that the recipient does not have an account. */}
              <Route path="/shared/:token" element={<SharedReport />} />
              <Route path="/analyze" element={<Protected><Analyze /></Protected>} />
              <Route path="/report/:id" element={<Protected><Report /></Protected>} />
              <Route path="/history" element={<Protected><History /></Protected>} />
              <Route path="/insights" element={<Protected><Dashboard /></Protected>} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </main>

        <footer className="border-t border-line py-6">
          <div className="mx-auto max-w-5xl px-5 text-2xs text-ink-muted sm:px-8">
            Verdicts are automated and can be wrong. Check the sources before
            relying on one.
          </div>
        </footer>
      </div>

      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onToggleTheme={toggleTheme}
        theme={theme}
      />
    </div>
  );
}

export default function App() {
  return (
    <Router>
      <AuthProvider>
        <Shell />
      </AuthProvider>
    </Router>
  );
}
