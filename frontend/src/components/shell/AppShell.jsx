import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  BarChart3, ChevronsLeft, Clock, Command, LogOut, Moon,
  PanelLeft, ScanSearch, ShieldCheck, Sun, User,
} from 'lucide-react';

import { Dropdown, Tooltip } from '../ui';
import { useAuth } from '../../contexts/AuthContext';

/**
 * The signed-in application frame.
 *
 * A rail on the desktop, a bottom bar on a phone -- not the same navigation
 * shrunk. The two have genuinely different constraints: a desktop rail can
 * afford persistent labels and a collapsed state, while a phone needs the
 * primary destinations within thumb reach and everything else behind the
 * account menu.
 *
 * Signed-out pages (the landing page, sign-in, a shared report) do not use
 * this. They get the marketing header instead, because a navigation rail
 * full of destinations you cannot visit is worse than no rail.
 */

const DESTINATIONS = [
  { to: '/analyze', label: 'Check', icon: ScanSearch, hint: 'Analyse a claim' },
  { to: '/history', label: 'History', icon: Clock, hint: 'Past checks' },
  { to: '/insights', label: 'Insights', icon: BarChart3, hint: 'Aggregate view' },
];

const COLLAPSE_KEY = 'ts.rail.collapsed';

function useCollapsed() {
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem(COLLAPSE_KEY) === '1'; } catch { return false; }
  });
  useEffect(() => {
    try { localStorage.setItem(COLLAPSE_KEY, collapsed ? '1' : '0'); } catch { /* private mode */ }
  }, [collapsed]);
  return [collapsed, () => setCollapsed((v) => !v)];
}

function Wordmark({ compact = false }) {
  return (
    <Link
      to="/analyze"
      className="focusable flex shrink-0 items-center gap-2.5 rounded-lg"
      aria-label="TruthShield"
    >
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-brand shadow-sm">
        <ShieldCheck className="h-4 w-4 text-white" aria-hidden="true" />
      </span>
      {!compact && (
        <span className="text-[0.9375rem] font-bold tracking-tight text-ink">TruthShield</span>
      )}
    </Link>
  );
}

/* ── Desktop rail ─────────────────────────────────────────── */

function Rail({ collapsed, onToggleCollapse }) {
  const { pathname } = useLocation();

  return (
    <aside
      className={`sticky top-0 hidden h-screen shrink-0 flex-col border-r border-line bg-surface/60 lg:flex ${
        collapsed ? 'w-[4.5rem]' : 'w-60'
      }`}
      style={{ transition: `width var(--t-slow) var(--ease)` }}
    >
      <div className={`flex h-14 items-center ${collapsed ? 'justify-center px-2' : 'px-4'}`}>
        <Wordmark compact={collapsed} />
      </div>

      <nav className="flex-1 space-y-0.5 px-2.5 py-3" aria-label="Main">
        {DESTINATIONS.map(({ to, label, icon: Icon, hint }) => {
          const active = pathname === to || pathname.startsWith(`${to}/`);
          const item = (
            <Link
              key={to}
              to={to}
              aria-current={active ? 'page' : undefined}
              className={`nav-item ${collapsed ? '!px-0 justify-center' : ''}`}
            >
              <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
              {!collapsed && <span className="truncate">{label}</span>}
            </Link>
          );
          // Collapsed, the icon is the only affordance left, so the label has
          // to come back on hover or the rail becomes a guessing game.
          return collapsed
            ? <Tooltip key={to} label={hint} side="right">{item}</Tooltip>
            : item;
        })}
      </nav>

      <div className="border-t border-line p-2.5">
        <button
          onClick={onToggleCollapse}
          className={`nav-item w-full ${collapsed ? '!px-0 justify-center' : ''}`}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <ChevronsLeft
            className={`h-4 w-4 shrink-0 transition-transform duration-[var(--t-slow)] ${collapsed ? 'rotate-180' : ''}`}
            aria-hidden="true"
          />
          {!collapsed && <span>Collapse</span>}
        </button>
      </div>
    </aside>
  );
}

/* ── Mobile bottom bar ────────────────────────────────────── */

function BottomBar() {
  const { pathname } = useLocation();

  return (
    <nav
      className="fixed inset-x-0 bottom-0 border-t border-line bg-page/95 lg:hidden"
      style={{
        zIndex: 'var(--z-nav)',
        // Clears the home indicator on a modern iPhone, where a flush bar
        // puts the tap targets under the system gesture area.
        paddingBottom: 'env(safe-area-inset-bottom)',
      }}
      aria-label="Main"
    >
      <div className="flex">
        {DESTINATIONS.map(({ to, label, icon: Icon }) => {
          const active = pathname === to || pathname.startsWith(`${to}/`);
          return (
            <Link
              key={to}
              to={to}
              aria-current={active ? 'page' : undefined}
              // 56px tall: comfortably past the 44px minimum touch target.
              className={`focusable flex flex-1 flex-col items-center gap-1 py-2.5 text-[0.6875rem] font-medium ${
                active ? 'text-brand' : 'text-ink-muted'
              }`}
            >
              <Icon className="h-[1.125rem] w-[1.125rem]" aria-hidden="true" />
              {label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

/* ── Top bar ──────────────────────────────────────────────── */

function TopBar({ theme, onToggleTheme, onOpenPalette }) {
  const { user, signOut } = useAuth();

  return (
    <header
      className="sticky top-0 border-b border-line bg-page/85 backdrop-blur-md"
      style={{ zIndex: 'var(--z-nav)' }}
    >
      <div className="flex h-14 items-center justify-between gap-3 px-4 sm:px-6">
        {/* The wordmark lives in the rail on desktop; on a phone there is no
            rail, so it comes back here. */}
        <div className="lg:hidden">
          <Wordmark />
        </div>

        <button
          onClick={onOpenPalette}
          className="focusable group ml-auto hidden h-9 items-center gap-2 rounded-xl border border-line bg-surface-sunken px-3 text-sm text-ink-muted transition-colors hover:border-[rgb(var(--c-border)/var(--border-alpha-strong))] hover:text-ink sm:flex lg:mr-auto lg:ml-0 lg:w-64"
          aria-label="Search past analyses"
        >
          <Command className="h-3.5 w-3.5" aria-hidden="true" />
          <span className="flex-1 text-left">Search…</span>
          <kbd className="rounded border border-line px-1.5 py-0.5 font-mono text-[0.625rem] text-ink-muted">
            ⌘K
          </kbd>
        </button>

        <div className="flex items-center gap-1">
          <Tooltip label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`} side="bottom">
            <button onClick={onToggleTheme} className="btn-ghost !p-2" aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}>
              {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
          </Tooltip>

          <Dropdown
            width={224}
            trigger={
              <button className="focusable flex h-8 w-8 items-center justify-center rounded-full bg-brand/15 text-[0.6875rem] font-bold uppercase text-brand" aria-label="Account">
                {(user?.email?.[0] || 'U')}
              </button>
            }
          >
            <div className="border-b border-line px-2.5 pb-2 pt-1.5">
              <div className="flex items-center gap-2">
                <User className="h-3.5 w-3.5 shrink-0 text-ink-muted" aria-hidden="true" />
                <span className="truncate text-[0.8125rem] text-ink" title={user?.email}>
                  {user?.email || 'Signed in'}
                </span>
              </div>
            </div>
            <div className="pt-1">
              <button onClick={signOut} className="menu-item" role="menuitem">
                <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
                Sign out
              </button>
            </div>
          </Dropdown>
        </div>
      </div>
    </header>
  );
}

/* ── Shell ────────────────────────────────────────────────── */

export default function AppShell({ theme, onToggleTheme, onOpenPalette, children }) {
  const [collapsed, toggleCollapsed] = useCollapsed();

  return (
    <div className="flex min-h-screen bg-page">
      <Rail collapsed={collapsed} onToggleCollapse={toggleCollapsed} />

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar theme={theme} onToggleTheme={onToggleTheme} onOpenPalette={onOpenPalette} />

        {/* The bottom padding clears the mobile bar, which is fixed and would
            otherwise sit on top of the last element on every page. */}
        <main className="flex-1 py-8 pb-24 sm:py-10 lg:pb-10">
          {children}
        </main>

        <footer className="hidden border-t border-line py-6 lg:block">
          <div className="px-6 text-[0.6875rem] text-ink-muted">
            Verdicts are automated and can be wrong. Check the sources before relying on one.
          </div>
        </footer>
      </div>

      <BottomBar />
    </div>
  );
}

export { DESTINATIONS, Wordmark };
