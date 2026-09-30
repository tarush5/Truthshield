import {
  ArrowLeftRight, BarChart3, Cpu, FileSearch, FileText, History, LayoutDashboard, Library, Link2,
  LogOut, Menu, Newspaper, Radar, ScanFace, Search, Settings, ShieldAlert, X,
  type LucideIcon,
} from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useState, type ReactNode } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';

import { Logo } from '@/components/landing/Logo';
import { cn } from '@/lib/format';
import { ALL_MODULES } from '@/lib/modules';
import { authService } from '@/services';
import { useAuth } from '@/stores/auth';

interface NavItem {
  label: string;
  to: string;
  icon: LucideIcon;
  moduleId?: string;
}

const SECTIONS: { title: string; items: NavItem[] }[] = [
  {
    title: 'Workspace',
    items: [
      { label: 'Dashboard', to: '/app', icon: LayoutDashboard },
      { label: 'Investigate', to: '/app/investigate', icon: Search },
      { label: 'Investigation History', to: '/app/history', icon: History },
    ],
  },
  {
    title: 'Intelligence',
    items: [
      { label: 'Threat Intelligence', to: '/app/m/threat-intel', icon: Radar, moduleId: 'threat-intel' },
      { label: 'Fraud Intelligence', to: '/app/m/fraud', icon: ShieldAlert, moduleId: 'fraud' },
      { label: 'Misinformation', to: '/app/m/misinformation', icon: Newspaper, moduleId: 'misinformation' },
      { label: 'Deepfake Detection', to: '/app/m/deepfake', icon: ScanFace, moduleId: 'deepfake' },
      { label: 'Document Forensics', to: '/app/m/documents', icon: FileSearch, moduleId: 'documents' },
      { label: 'URL Intelligence', to: '/app/url-intelligence', icon: Link2 },
      { label: 'Transaction Analysis', to: '/app/m/transactions', icon: ArrowLeftRight, moduleId: 'transactions' },
    ],
  },
  {
    title: 'Evidence & insight',
    items: [
      { label: 'Evidence', to: '/app/m/rag', icon: Library, moduleId: 'rag' },
      { label: 'Reports', to: '/app/m/reports', icon: FileText, moduleId: 'reports' },
      { label: 'Analytics', to: '/app/m/analytics', icon: BarChart3, moduleId: 'analytics' },
      { label: 'Model Intelligence', to: '/app/m/models', icon: Cpu, moduleId: 'models' },
    ],
  },
];

function phaseTag(moduleId?: string) {
  const mod = moduleId ? ALL_MODULES.find((m) => m.id === moduleId) : undefined;
  if (!mod || mod.availability === 'live') return null;
  return mod.availability === 'planned' ? `P${mod.phase}` : 'Partial';
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const user = useAuth((s) => s.user);
  const refreshToken = useAuth((s) => s.refreshToken);
  const clear = useAuth((s) => s.clear);
  const navigate = useNavigate();

  const signOut = async () => {
    if (refreshToken) {
      try {
        await authService.logout(refreshToken);
      } catch {
        /* sign out locally regardless */
      }
    }
    clear();
    navigate('/');
  };

  return (
    <div className="flex h-full flex-col">
      <Link to="/" className="flex items-center gap-3 px-5 pb-6 pt-6" onClick={onNavigate}>
        <Logo size="sm" />
        <span className="text-[15px] font-medium tracking-tight text-text-primary">
          TruthShield <span className="font-display italic text-muted">2.0</span>
        </span>
      </Link>

      <nav aria-label="Application" className="scrollbar-none flex-1 overflow-y-auto px-3 pb-4">
        {SECTIONS.map((section) => (
          <div key={section.title} className="mb-5">
            <p className="mb-2 px-3 text-[10px] uppercase tracking-[0.25em] text-muted/80">{section.title}</p>
            <ul className="space-y-0.5">
              {section.items.map((item) => {
                const tag = phaseTag(item.moduleId);
                return (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      end={item.to === '/app'}
                      onClick={onNavigate}
                      className={({ isActive }) =>
                        cn(
                          'group flex items-center gap-3 rounded-full px-3 py-2 text-sm transition-colors',
                          isActive ? 'bg-stroke/70 text-text-primary' : 'text-muted hover:bg-stroke/40 hover:text-text-primary',
                        )
                      }
                    >
                      {({ isActive }) => (
                        <>
                          <span className={cn('flex h-6 w-6 items-center justify-center rounded-full', isActive && 'accent-gradient text-bg')}>
                            <item.icon className="h-3.5 w-3.5" aria-hidden />
                          </span>
                          <span className="flex-1 truncate">{item.label}</span>
                          {tag && <span className="text-[10px] uppercase tracking-wider text-muted/70">{tag}</span>}
                        </>
                      )}
                    </NavLink>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="border-t border-stroke p-3">
        <NavLink
          to="/app/settings"
          onClick={onNavigate}
          className={({ isActive }) => cn('flex items-center gap-3 rounded-full px-3 py-2 text-sm', isActive ? 'bg-stroke/70 text-text-primary' : 'text-muted hover:bg-stroke/40 hover:text-text-primary')}
        >
          <Settings className="h-4 w-4" aria-hidden /> Settings
        </NavLink>
        <div className="mt-2 flex items-center gap-3 rounded-2xl px-3 py-2">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-stroke text-xs font-medium uppercase text-text-primary">
            {user?.email?.[0] ?? '?'}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs text-text-primary">{user?.email}</p>
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted">{user?.role ?? 'USER'}</p>
          </div>
          <button onClick={signOut} className="rounded-full p-2 text-muted hover:bg-stroke/60 hover:text-text-primary" aria-label="Sign out" title="Sign out">
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const location = useLocation();

  useEffect(() => setOpen(false), [location.pathname]);

  return (
    <div className="min-h-screen bg-bg">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 border-r border-stroke bg-bg lg:block">
        <SidebarContent />
      </aside>

      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-stroke bg-bg/85 px-4 py-3 backdrop-blur-md lg:hidden">
        <Link to="/app" className="flex items-center gap-2">
          <Logo size="sm" />
          <span className="text-sm font-medium">TruthShield</span>
        </Link>
        <button onClick={() => setOpen(true)} className="rounded-full p-2 text-muted hover:text-text-primary" aria-label="Open navigation">
          <Menu className="h-5 w-5" />
        </button>
      </header>

      <AnimatePresence>
        {open && (
          <>
            <motion.div className="fixed inset-0 z-40 bg-black/70 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setOpen(false)} />
            <motion.aside
              className="fixed inset-y-0 left-0 z-50 w-72 border-r border-stroke bg-bg lg:hidden"
              initial={{ x: -300 }}
              animate={{ x: 0 }}
              exit={{ x: -300 }}
              transition={{ type: 'spring', damping: 30, stiffness: 300 }}
            >
              <button onClick={() => setOpen(false)} className="absolute right-3 top-5 rounded-full p-2 text-muted hover:text-text-primary" aria-label="Close navigation">
                <X className="h-5 w-5" />
              </button>
              <SidebarContent onNavigate={() => setOpen(false)} />
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      <main className="lg:pl-64">
        <div className="mx-auto max-w-[1280px] px-4 py-8 sm:px-6 md:py-10 lg:px-10">{children}</div>
      </main>
    </div>
  );
}
