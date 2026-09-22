import React, { Suspense, lazy, useEffect, useState } from 'react';
import {
  BrowserRouter as Router, Link, Navigate, Route, Routes, useLocation,
} from 'react-router-dom';
import { Loader2, LogOut, Moon, Shield, Sun } from 'lucide-react';

import { AuthProvider, useAuth } from './contexts/AuthContext';

// Everything behind auth is split out, so a signed-out visitor does not
// download the report and history code to see the sign-in form.
const Analyze = lazy(() => import('./pages/Analyze'));
const Report = lazy(() => import('./pages/Report'));
const History = lazy(() => import('./pages/History'));
const Login = lazy(() => import('./pages/Login'));

function Fallback() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <Loader2 className="h-6 w-6 animate-spin text-brand-500" />
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

function NavBar() {
  const { user, signOut } = useAuth();
  const [theme, toggleTheme] = useTheme();
  const { pathname } = useLocation();

  return (
    <nav className="sticky top-0 z-50 border-b border-line bg-page/80 backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link to="/" className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-brand-500">
            <Shield className="h-4 w-4 text-white" />
          </span>
          <span className="text-base font-bold tracking-tight text-ink">TruthShield</span>
        </Link>

        <div className="flex items-center gap-1">
          {user && (
            <div className="mr-2 hidden items-center gap-1 sm:flex">
              {[
                { to: '/analyze', label: 'Check' },
                { to: '/history', label: 'History' },
              ].map(({ to, label }) => (
                <Link
                  key={to}
                  to={to}
                  className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                    pathname === to
                      ? 'bg-brand-500/12 text-brand-400'
                      : 'text-ink-muted hover:bg-white/[0.04] hover:text-ink'
                  }`}
                >
                  {label}
                </Link>
              ))}
            </div>
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
            <Link to="/login" className="btn-primary !px-4 !py-1.5 text-sm">Sign in</Link>
          )}
        </div>
      </div>
    </nav>
  );
}

function Protected({ children }) {
  const { isAuthenticated, checking } = useAuth();
  const location = useLocation();

  // Wait for the session check before redirecting, otherwise a reload on a
  // protected page bounces the user to sign-in for a frame.
  if (checking) return <Fallback />;
  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: location }} />;
  return children;
}

function Shell() {
  return (
    <div className="min-h-screen bg-page">
      <div className="bg-radial-glow pointer-events-none fixed inset-0" aria-hidden="true" />
      <div className="relative z-10">
        <NavBar />
        <main className="py-8 sm:py-12">
          <Suspense fallback={<Fallback />}>
            <Routes>
              <Route path="/" element={<Navigate to="/analyze" replace />} />
              <Route path="/login" element={<Login />} />
              <Route path="/analyze" element={<Protected><Analyze /></Protected>} />
              <Route path="/report/:id" element={<Protected><Report /></Protected>} />
              <Route path="/history" element={<Protected><History /></Protected>} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </main>
      </div>
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
