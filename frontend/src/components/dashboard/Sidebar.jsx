import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LayoutDashboard, Search, Clock, Settings,
  LogOut, ChevronLeft, ChevronRight, Shield, User
} from 'lucide-react';

// Focused navigation — only real, working features
const NAV_ITEMS = [
  { id: 'overview',  label: 'Dashboard',   icon: LayoutDashboard, description: 'Overview & analytics' },
  { id: 'analyze',   label: 'Analyze',     icon: Search,          description: 'Verify content' },
  { id: 'history',   label: 'History',     icon: Clock,           description: 'Past analyses' },
];

/**
 * Sidebar — collapsible navigation panel (product-focused)
 * @param {string}   activeView   - Currently active view ID
 * @param {function} onViewChange - Callback when nav item is clicked
 * @param {boolean}  collapsed    - External collapse state
 * @param {function} onCollapse   - Toggle collapse callback
 */
export default function Sidebar({ activeView, onViewChange, collapsed, onCollapse }) {
  const orgName = localStorage.getItem('active_org_name') || 'Personal Workspace';
  const userStr = localStorage.getItem('user');
  const user = userStr ? JSON.parse(userStr) : null;
  const userEmail = user?.email || 'user@example.com';

  // Profile menu state
  const [profileOpen, setProfileOpen] = useState(false);
  const profileRef = useRef(null);

  // Close profile menu on outside click
  useEffect(() => {
    const handler = (e) => {
      if (profileRef.current && !profileRef.current.contains(e.target)) {
        setProfileOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    localStorage.removeItem('active_org_id');
    localStorage.removeItem('active_org_name');
    window.location.href = '/';
  };

  // First two letters of org name for avatar
  const orgInitials = orgName.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
  const userInitial = userEmail[0]?.toUpperCase() || 'U';

  return (
    <motion.aside
      initial={false}
      animate={{ width: collapsed ? 76 : 260 }}
      transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
      className="fixed left-4 top-4 bottom-4 z-40 flex flex-col
                 bg-[#071124]/45 backdrop-blur-2xl border border-white/10 rounded-2xl
                 overflow-hidden select-none shadow-2xl"
    >
      {/* ── Brand Header ── */}
      <div className="p-4 border-b border-white/[0.06]">
        <div className="flex items-center gap-3">
          {/* Logo */}
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-500 to-cyan-500 
                          flex items-center justify-center shrink-0 shadow-lg shadow-brand-500/20
                          relative group">
            <Shield className="w-[18px] h-[18px] text-white" />
            <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-brand-400 to-cyan-400 
                            opacity-0 group-hover:opacity-30 blur transition-opacity duration-300" />
          </div>

          <AnimatePresence>
            {!collapsed && (
              <motion.div
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -8 }}
                transition={{ duration: 0.2 }}
                className="flex flex-col min-w-0"
              >
                <span className="text-sm font-bold text-white tracking-tight">TruthShield</span>
                <span className="text-[10px] text-white/35 flex items-center gap-1 mt-0.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  {orgName}
                </span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* ── Section Label ── */}
      <AnimatePresence>
        {!collapsed && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="px-5 pt-5 pb-1"
          >
            <span className="text-[10px] font-semibold uppercase tracking-[0.15em] text-white/20">
              Main Menu
            </span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Navigation ── */}
      <nav className="flex-1 py-2 px-2 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const isActive = activeView === item.id;
          const Icon = item.icon;

          return (
            <button
              key={item.id}
              onClick={() => onViewChange(item.id)}
              className={`
                relative w-full flex items-center gap-3 rounded-xl
                transition-all duration-200 group
                ${collapsed ? 'px-0 py-3 justify-center' : 'px-3 py-2.5'}
                ${isActive
                  ? 'bg-brand-500/10 text-white'
                  : 'text-white/45 hover:text-white hover:bg-white/[0.04]'
                }
              `}
            >
              {/* Active left bar indicator */}
              {isActive && (
                <motion.div
                  layoutId="sidebar-indicator"
                  className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 
                             bg-gradient-to-b from-brand-400 to-cyan-400 rounded-r-full"
                  transition={{ type: 'spring', stiffness: 500, damping: 35 }}
                />
              )}

              <div className={`relative flex items-center justify-center w-[22px] h-[22px] shrink-0`}>
                <Icon className={`w-[18px] h-[18px] transition-colors duration-200
                  ${isActive ? 'text-brand-400' : 'text-white/40 group-hover:text-white/70'}`}
                />
                {/* Active glow */}
                {isActive && (
                  <div className="absolute inset-0 bg-brand-400/20 rounded-full blur-md" />
                )}
              </div>

              <AnimatePresence>
                {!collapsed && (
                  <motion.div
                    initial={{ opacity: 0, x: -4 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -4 }}
                    transition={{ duration: 0.15 }}
                    className="flex flex-col items-start min-w-0"
                  >
                    <span className={`text-[13px] font-medium whitespace-nowrap
                      ${isActive ? 'text-white' : ''}`}>
                      {item.label}
                    </span>
                    {isActive && (
                      <motion.span
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="text-[10px] text-white/30 whitespace-nowrap"
                      >
                        {item.description}
                      </motion.span>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Tooltip for collapsed state */}
              {collapsed && (
                <div className="absolute left-full ml-2 px-2.5 py-1.5 rounded-lg bg-surface-800 
                                border border-white/10 text-xs text-white font-medium
                                opacity-0 group-hover:opacity-100 pointer-events-none
                                transition-opacity whitespace-nowrap z-50 shadow-xl">
                  {item.label}
                  <div className="absolute left-0 top-1/2 -translate-x-1 -translate-y-1/2 
                                  w-2 h-2 rotate-45 bg-surface-800 border-l border-b border-white/10" />
                </div>
              )}
            </button>
          );
        })}
      </nav>

      {/* ── Bottom: User Profile + Collapse ── */}
      <div className="border-t border-white/[0.06] p-3 space-y-2" ref={profileRef}>
        {/* User profile row */}
        <div className="relative">
          <button
            onClick={() => setProfileOpen(p => !p)}
            className={`w-full flex items-center gap-2.5 rounded-xl p-2 
                        hover:bg-white/[0.04] transition-all duration-200 group
                        ${collapsed ? 'justify-center' : ''}
                        ${profileOpen ? 'bg-white/[0.04]' : ''}`}
          >
            {/* Avatar */}
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500/20 to-cyan-500/20 
                            flex items-center justify-center border border-white/[0.08] shrink-0
                            group-hover:border-brand-500/30 transition-colors">
              <span className="text-[11px] font-bold text-brand-300">{userInitial}</span>
            </div>

            <AnimatePresence>
              {!collapsed && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="flex-1 min-w-0 text-left"
                >
                  <p className="text-xs text-white/70 font-medium truncate">{userEmail}</p>
                  <p className="text-[10px] text-white/25 truncate">Click to manage</p>
                </motion.div>
              )}
            </AnimatePresence>
          </button>

          {/* Profile popover menu */}
          <AnimatePresence>
            {profileOpen && (
              <motion.div
                initial={{ opacity: 0, y: 8, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 8, scale: 0.95 }}
                transition={{ duration: 0.15 }}
                className={`absolute bottom-full mb-2 z-50 
                            bg-[#0c1a2e]/95 backdrop-blur-2xl rounded-xl 
                            border border-white/10 shadow-2xl overflow-hidden
                            ${collapsed ? 'left-0 w-48' : 'left-0 right-0'}`}
              >
                {/* User info header */}
                <div className="px-3 py-2.5 border-b border-white/[0.06]">
                  <p className="text-xs font-semibold text-white truncate">{userEmail}</p>
                  <p className="text-[10px] text-white/30 mt-0.5">{orgName}</p>
                </div>

                {/* Menu items */}
                <div className="py-1">
                  <button
                    onClick={() => { onViewChange('settings'); setProfileOpen(false); }}
                    className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-white/60 
                               hover:text-white hover:bg-white/[0.04] transition-all"
                  >
                    <Settings className="w-3.5 h-3.5" />
                    Settings
                  </button>
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-red-400/70 
                               hover:text-red-400 hover:bg-red-500/[0.06] transition-all"
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    Sign out
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Collapse toggle */}
        <button
          onClick={onCollapse}
          className="w-full flex items-center justify-center py-2 rounded-lg 
                     bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.06]
                     text-white/30 hover:text-white/60 transition-all"
        >
          {collapsed
            ? <ChevronRight className="w-4 h-4" />
            : <ChevronLeft className="w-4 h-4" />
          }
        </button>
      </div>
    </motion.aside>
  );
}
