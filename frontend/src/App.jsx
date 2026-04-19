import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Shield, BarChart3, Search, Globe, Menu, X } from 'lucide-react';
import Analyze from './pages/Analyze';
import Report from './pages/Report';
import Dashboard from './pages/Dashboard';

function NavBar() {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  const navLinks = [
    { path: '/', label: t('nav.analyze'), icon: Search },
    { path: '/dashboard', label: t('nav.dashboard'), icon: BarChart3 },
  ];

  const changeLang = (lang) => {
    i18n.changeLanguage(lang);
  };

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 border-b border-white/5">
      <div className="absolute inset-0 bg-surface-900/80 backdrop-blur-xl" />
      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-3 group">
            <div className="relative">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-500 to-cyan-500 flex items-center justify-center shadow-lg shadow-brand-500/25 group-hover:shadow-brand-500/40 transition-shadow">
                <Shield className="w-5 h-5 text-white" />
              </div>
              <div className="absolute -inset-1 rounded-xl bg-gradient-to-br from-brand-500 to-cyan-500 opacity-0 group-hover:opacity-20 blur transition-opacity" />
            </div>
            <span className="text-lg font-bold font-display gradient-text">{t('app_name')}</span>
          </Link>

          {/* Desktop Nav */}
          <div className="hidden md:flex items-center gap-1">
            {navLinks.map(({ path, label, icon: Icon }) => (
              <Link
                key={path}
                to={path}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                  location.pathname === path
                    ? 'bg-brand-500/10 text-brand-400'
                    : 'text-white/60 hover:text-white hover:bg-white/5'
                }`}
              >
                <Icon className="w-4 h-4" />
                {label}
              </Link>
            ))}
          </div>

          {/* Language Switcher + Mobile Toggle */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1 bg-white/5 rounded-lg p-1">
              {['en', 'hi', 'ta'].map((lang) => (
                <button
                  key={lang}
                  onClick={() => changeLang(lang)}
                  className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-all duration-200 ${
                    i18n.language === lang
                      ? 'bg-brand-500 text-white shadow-sm'
                      : 'text-white/50 hover:text-white hover:bg-white/5'
                  }`}
                >
                  {lang.toUpperCase()}
                </button>
              ))}
            </div>

            <button
              onClick={() => setMobileOpen(!mobileOpen)}
              className="md:hidden p-2 text-white/60 hover:text-white"
            >
              {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {/* Mobile Nav */}
        {mobileOpen && (
          <div className="md:hidden pb-4 border-t border-white/5 mt-2 pt-3">
            {navLinks.map(({ path, label, icon: Icon }) => (
              <Link
                key={path}
                to={path}
                onClick={() => setMobileOpen(false)}
                className={`flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                  location.pathname === path
                    ? 'bg-brand-500/10 text-brand-400'
                    : 'text-white/60 hover:text-white hover:bg-white/5'
                }`}
              >
                <Icon className="w-4 h-4" />
                {label}
              </Link>
            ))}
          </div>
        )}
      </div>
    </nav>
  );
}

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-surface-900 bg-grid">
        <div className="bg-radial-glow fixed inset-0 pointer-events-none" />
        <NavBar />
        <main className="relative pt-20 pb-12">
          <Routes>
            <Route path="/" element={<Analyze />} />
            <Route path="/analyze" element={<Analyze />} />
            <Route path="/report/:id" element={<Report />} />
            <Route path="/dashboard" element={<Dashboard />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
