import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation, Navigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Shield, BarChart3, Search, Menu, X, Sun, Moon } from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';

import { AuthProvider, useAuth } from './contexts/AuthContext';
import Analyze from './pages/Analyze';
import Report from './pages/Report';
import Dashboard from './pages/Dashboard';
import Login from './pages/Login';
import Landing from './pages/Landing';
import AuthCallback from './pages/AuthCallback';
import CyberBackground from './components/CyberBackground';
import CursorTrail from './components/CursorTrail';
/* ─────────── NavBar ─────────── */
function NavBar() {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const { user, activeOrg, signOut } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'dark');
  const [scrolled, setScrolled] = useState(false);

  // Theme toggle
  useEffect(() => {
    if (theme === 'light') {
      document.documentElement.classList.add('light');
    } else {
      document.documentElement.classList.remove('light');
    }
    localStorage.setItem('theme', theme);
  }, [theme]);

  // Scroll detection for navbar transparency
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const isLanding = location.pathname === '/';
  const isDashboard = location.pathname === '/dashboard';

  // Hide navbar on dashboard (it has its own sidebar)
  if (isDashboard) return null;

  const navLinks = [
    { path: '/analyze', label: t('nav.analyze') || 'Analyze', icon: Search },
    { path: '/dashboard', label: t('nav.dashboard') || 'Dashboard', icon: BarChart3 },
  ];

  const handleLogout = async () => {
    await signOut();
    window.location.href = '/';
  };

  return (
    <nav className={`fixed top-0 left-0 right-0 z-50 border-b transition-all duration-500 ${
      scrolled || !isLanding
        ? 'border-white/[0.06] bg-black/80 backdrop-blur-2xl'
        : 'border-transparent bg-transparent'
    }`}>
      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-3 group">
            <div className="relative">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-red-600 to-red-900 flex items-center justify-center shadow-lg shadow-red-500/20 group-hover:shadow-red-500/40 transition-all duration-300">
                <Shield className="w-5 h-5 text-white" />
              </div>
              <div className="absolute -inset-1 rounded-xl bg-red-500 opacity-0 group-hover:opacity-15 blur-md transition-opacity duration-500" />
            </div>
            <div className="flex flex-col items-start leading-none">
              <span className="text-lg font-bold gradient-text" style={{ fontFamily: 'Orbitron, sans-serif' }}>{t('app_name') || 'TruthShield'}</span>
              {activeOrg.name && (
                <span className="text-[10px] text-white/40 mt-0.5 font-medium flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-500 pulse-red" />
                  {activeOrg.name}
                </span>
              )}
            </div>
          </Link>

          {/* Desktop Nav */}
          <div className="hidden md:flex items-center gap-1">
            {!isLanding && navLinks.map(({ path, label, icon: Icon }) => (
              <Link
                key={path}
                to={path}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-300 ${
                  location.pathname === path
                    ? 'bg-red-500/10 text-red-400 border border-red-500/20'
                    : 'text-white/60 hover:text-white hover:bg-white/[0.04]'
                }`}
              >
                <Icon className="w-4 h-4" />
                {label}
              </Link>
            ))}
          </div>

          {/* Right Controls */}
          <div className="flex items-center gap-3">
            {/* Theme Toggle */}
            <button
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              className="p-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-white/50 hover:text-red-400 transition-all duration-300 border border-white/[0.06]"
              aria-label="Toggle Theme"
            >
              {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>

            {/* Language */}
            <div className="hidden sm:flex items-center gap-1 bg-white/[0.04] rounded-lg p-1 border border-white/[0.06]">
              {['en', 'hi', 'ta'].map((lang) => (
                <button
                  key={lang}
                  onClick={() => i18n.changeLanguage(lang)}
                  className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-all duration-300 ${
                    i18n.language === lang
                      ? 'bg-red-600 text-white shadow-sm shadow-red-500/20'
                      : 'text-white/50 hover:text-white hover:bg-white/[0.06]'
                  }`}
                >
                  {lang.toUpperCase()}
                </button>
              ))}
            </div>

            {/* Auth Buttons */}
            {user ? (
              <div className="hidden md:flex items-center gap-3">
                <span className="text-xs text-white/50 font-medium truncate max-w-[120px]" style={{ fontFamily: 'JetBrains Mono, monospace' }}>{user.email}</span>
                <button
                  onClick={handleLogout}
                  className="px-3.5 py-1.5 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 text-xs font-semibold transition-all duration-300 border border-red-500/20 hover:border-red-500/40"
                >
                  Logout
                </button>
              </div>
            ) : (
              <Link
                to="/login"
                className="hidden md:block px-4 py-2 rounded-lg bg-gradient-to-r from-red-600 to-red-700 hover:from-red-500 hover:to-red-600 text-white text-xs font-bold tracking-wider shadow-lg shadow-red-500/20 hover:shadow-red-500/40 transition-all duration-300"
                style={{ fontFamily: 'Orbitron, sans-serif', fontSize: '10px' }}
              >
                ACCESS PLATFORM
              </Link>
            )}

            {/* Mobile toggle */}
            <button
              onClick={() => setMobileOpen(!mobileOpen)}
              className="md:hidden p-2 text-white/60 hover:text-white"
            >
              {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {/* Mobile Nav */}
        <AnimatePresence>
          {mobileOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="md:hidden overflow-hidden border-t border-white/5"
            >
              <div className="py-3 space-y-1">
                {navLinks.map(({ path, label, icon: Icon }) => (
                  <Link
                    key={path}
                    to={path}
                    onClick={() => setMobileOpen(false)}
                    className={`flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                      location.pathname === path
                        ? 'bg-red-500/10 text-red-400 border border-red-500/20'
                        : 'text-white/60 hover:text-white hover:bg-white/5'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    {label}
                  </Link>
                ))}

                <div className="border-t border-white/5 mt-3 pt-3 px-4 flex items-center justify-between">
                  {user ? (
                    <>
                      <span className="text-xs text-white/55 font-medium truncate max-w-[180px]">{user.email}</span>
                      <button onClick={handleLogout} className="px-3 py-1.5 rounded-lg bg-red-500/10 text-red-400 text-xs font-semibold">
                        Logout
                      </button>
                    </>
                  ) : (
                    <Link to="/login" onClick={() => setMobileOpen(false)} className="w-full text-center py-2.5 rounded-lg bg-gradient-to-r from-red-600 to-red-700 hover:from-red-500 hover:to-red-600 text-white text-xs font-semibold shadow-md shadow-red-500/20 transition-all">
                      Login
                    </Link>
                  )}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </nav>
  );
}

/* ─────────── Protected Route ─────────── */
function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();
  
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-red-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) {
    // Fallback: check localStorage for backward compatibility
    const token = localStorage.getItem('token');
    if (!token) return <Navigate to="/login" replace />;
  }

  return children;
}

/* ─────────── App ─────────── */
function AppContent() {
  const location = useLocation();
  const isDashboard = location.pathname === '/dashboard';

  return (
    <div className={`min-h-screen bg-black ${isDashboard ? '' : 'bg-grid'} relative overflow-hidden`}>
      <CyberBackground />
      <CursorTrail />
      {!isDashboard && <div className="bg-radial-glow fixed inset-0 pointer-events-none z-0" />}
      {!isDashboard && <NavBar />}
      <main className={`relative z-10 ${isDashboard ? '' : 'pt-20 pb-12'}`}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/auth/callback" element={<AuthCallback />} />
          <Route path="/analyze" element={<ProtectedRoute><Analyze /></ProtectedRoute>} />
          <Route path="/report/:id" element={<ProtectedRoute><Report /></ProtectedRoute>} />
          <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <Router>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </Router>
  );
}
