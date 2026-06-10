import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LayoutDashboard, Search, FileText, Globe, Users, Key, Settings,
  LogOut, ChevronLeft, ChevronRight, Shield
} from 'lucide-react';

// Navigation items config
const NAV_ITEMS = [
  { id: 'overview',  label: 'Overview',    icon: LayoutDashboard },
  { id: 'analyze',   label: 'Analyze',     icon: Search },
  { id: 'reports',   label: 'Reports',     icon: FileText },
  { id: 'threats',   label: 'Threat Map',  icon: Globe },
  { id: 'team',      label: 'Team',        icon: Users },
  { id: 'apikeys',   label: 'API Keys',    icon: Key },
  { id: 'settings',  label: 'Settings',    icon: Settings },
];

/**
 * Sidebar — collapsible navigation panel
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

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    localStorage.removeItem('active_org_id');
    localStorage.removeItem('active_org_name');
    window.location.href = '/';
  };

  // First two letters of org name for avatar
  const orgInitials = orgName.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();

  return (
    <motion.aside
      initial={false}
      animate={{ width: collapsed ? 72 : 260 }}
      transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
      className="h-screen fixed left-0 top-0 z-40 flex flex-col
                 bg-white/[0.03] backdrop-blur-2xl border-r border-white/[0.06]
                 overflow-hidden select-none"
    >
      {/* ── Workspace Switcher ── */}
      <div className="p-4 border-b border-white/[0.06]">
        <div className="flex items-center gap-3">
          {/* Gradient avatar */}
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-500 to-cyan-500 
                          flex items-center justify-center shrink-0 shadow-lg shadow-brand-500/20">
            <span className="text-xs font-bold text-white">{orgInitials}</span>
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
                <span className="text-sm font-semibold text-white truncate">{orgName}</span>
                <span className="text-[10px] text-white/35 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Active
                </span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* ── Navigation ── */}
      <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto">
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
                ${collapsed ? 'px-0 py-2.5 justify-center' : 'px-3 py-2.5'}
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
                             bg-brand-500 rounded-r-full"
                  transition={{ type: 'spring', stiffness: 500, damping: 35 }}
                />
              )}

              <Icon className={`w-[18px] h-[18px] shrink-0 transition-colors
                ${isActive ? 'text-brand-400' : 'text-white/40 group-hover:text-white/70'}`}
              />

              <AnimatePresence>
                {!collapsed && (
                  <motion.span
                    initial={{ opacity: 0, x: -4 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -4 }}
                    transition={{ duration: 0.15 }}
                    className={`text-[13px] font-medium whitespace-nowrap
                      ${isActive ? 'text-white' : ''}`}
                  >
                    {item.label}
                  </motion.span>
                )}
              </AnimatePresence>

              {/* Tooltip for collapsed state */}
              {collapsed && (
                <div className="absolute left-full ml-2 px-2.5 py-1 rounded-lg bg-surface-800 
                                border border-white/10 text-xs text-white font-medium
                                opacity-0 group-hover:opacity-100 pointer-events-none
                                transition-opacity whitespace-nowrap z-50 shadow-xl">
                  {item.label}
                </div>
              )}
            </button>
          );
        })}
      </nav>

      {/* ── Bottom: Collapse Toggle + User ── */}
      <div className="border-t border-white/[0.06] p-3 space-y-2">
        {/* User info */}
        <div className={`flex items-center gap-2.5 ${collapsed ? 'justify-center' : ''}`}>
          <div className="w-8 h-8 rounded-lg bg-white/[0.06] flex items-center justify-center 
                          border border-white/[0.08] shrink-0">
            <span className="text-[11px] font-bold text-white/60">
              {userEmail[0]?.toUpperCase()}
            </span>
          </div>

          <AnimatePresence>
            {!collapsed && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex-1 min-w-0"
              >
                <p className="text-xs text-white/70 font-medium truncate">{userEmail}</p>
              </motion.div>
            )}
          </AnimatePresence>

          {!collapsed && (
            <button
              onClick={handleLogout}
              className="p-1.5 rounded-lg hover:bg-red-500/10 text-white/30 
                         hover:text-red-400 transition-all shrink-0"
              title="Logout"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          )}
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
