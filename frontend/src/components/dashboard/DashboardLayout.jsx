import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Menu, X } from 'lucide-react';
import Sidebar from './Sidebar';

// Map view IDs to display titles
const VIEW_TITLES = {
  overview: 'Overview',
  analyze:  'Analyze Content',
  history:  'Analysis History',
  settings: 'Settings',
};

/**
 * DashboardLayout — responsive shell with sidebar + main content area
 * @param {ReactNode} children     - Content to render in the main area
 * @param {string}    activeView   - Current view identifier
 * @param {function}  onViewChange - Callback when sidebar nav changes
 */
export default function DashboardLayout({ children, activeView, onViewChange }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  // Track screen width for responsive behavior
  useEffect(() => {
    const check = () => {
      const mobile = window.innerWidth < 1024;
      setIsMobile(mobile);
      if (mobile) setCollapsed(true);
    };
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);

  // Close mobile overlay when view changes
  const handleViewChange = (view) => {
    onViewChange(view);
    if (isMobile) setMobileOpen(false);
  };

  const sidebarWidth = collapsed ? 76 + 16 : 260 + 16;

  return (
    <div className="min-h-screen bg-surface-900">
      {/* ── Desktop Sidebar ── */}
      {!isMobile && (
        <Sidebar
          activeView={activeView}
          onViewChange={handleViewChange}
          collapsed={collapsed}
          onCollapse={() => setCollapsed(c => !c)}
        />
      )}

      {/* ── Mobile Sidebar Overlay ── */}
      <AnimatePresence>
        {isMobile && mobileOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setMobileOpen(false)}
              className="fixed inset-0 z-30 bg-black/60 backdrop-blur-sm"
            />
            {/* Sidebar */}
            <motion.div
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: 'spring', damping: 30, stiffness: 300 }}
              className="fixed left-0 top-0 z-40"
            >
              <Sidebar
                activeView={activeView}
                onViewChange={handleViewChange}
                collapsed={false}
                onCollapse={() => setMobileOpen(false)}
              />
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* ── Main Content Area ── */}
      <motion.div
        initial={false}
        animate={{ marginLeft: isMobile ? 0 : sidebarWidth }}
        transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
        className="min-h-screen flex flex-col"
      >
        {/* Top Bar */}
        <header className="sticky top-0 z-20 border-b border-white/[0.06]
                           bg-surface-900/80 backdrop-blur-xl">
          <div className="flex items-center justify-between h-14 px-6">
            <div className="flex items-center gap-3">
              {/* Mobile hamburger */}
              {isMobile && (
                <button
                  onClick={() => setMobileOpen(true)}
                  className="p-2 -ml-2 rounded-lg hover:bg-white/5 text-white/50 
                             hover:text-white transition-colors"
                >
                  <Menu className="w-5 h-5" />
                </button>
              )}

              {/* Breadcrumb */}
              <div className="flex items-center gap-2 text-sm">
                <span className="text-white/30 font-medium">Dashboard</span>
                <span className="text-white/15">/</span>
                <span className="text-white font-semibold">
                  {VIEW_TITLES[activeView] || 'Overview'}
                </span>
              </div>
            </div>

            {/* Search placeholder */}
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-xl 
                            bg-white/[0.04] border border-white/[0.06] text-white/25 
                            hover:border-white/10 transition-colors cursor-pointer w-64">
              <Search className="w-3.5 h-3.5" />
              <span className="text-xs font-medium">Search anything...</span>
              <div className="ml-auto flex items-center gap-0.5">
                <kbd className="px-1.5 py-0.5 rounded bg-white/[0.06] text-[10px] 
                                font-mono text-white/30">⌘</kbd>
                <kbd className="px-1.5 py-0.5 rounded bg-white/[0.06] text-[10px] 
                                font-mono text-white/30">K</kbd>
              </div>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 p-6">
          {children}
        </main>
      </motion.div>
    </div>
  );
}
