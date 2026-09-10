import clsx from 'clsx';
import {
  Archive,
  LayoutDashboard,
  LogOut,
  Menu,
  Monitor,
  Moon,
  Scale,
  ScanLine,
  Settings,
  Sun,
  Users,
  Wifi,
  WifiOff,
  X,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';

import { useAuth } from '../../context/AuthContext';
import { useI18n } from '../../context/I18nContext';
import { useTheme } from '../../context/ThemeContext';
import { api } from '../../lib/api';
import { Badge, Button } from '../ui';

/** `role` is the minimum rank required; the server enforces the same thresholds. */
const NAV = [
  { to: '/', end: true, icon: LayoutDashboard, key: 'nav.dashboard', role: 'INSPECTOR' },
  { to: '/scan', icon: ScanLine, key: 'nav.scan', role: 'INSPECTOR' },
  { to: '/repository', icon: Archive, key: 'nav.repository', role: 'INSPECTOR' },
  { to: '/rules', icon: Scale, key: 'nav.rules', role: 'INSPECTOR' },
  { to: '/officers', icon: Users, key: 'nav.users', role: 'ADMIN' },
  { to: '/settings', icon: Settings, key: 'nav.settings', role: 'INSPECTOR' },
];

/** Bottom bar on phones: the four things an inspector needs in the field. */
const MOBILE_NAV = NAV.filter((item) => ['/', '/scan', '/repository', '/settings'].includes(item.to));

function Emblem({ className }) {
  return (
    <div
      className={clsx(
        'grid place-items-center rounded bg-brand text-brand-ink font-semibold shrink-0',
        className,
      )}
      aria-hidden
    >
      <svg viewBox="0 0 24 24" fill="none" className="h-[60%] w-[60%]">
        <path
          d="M12 3v18M5 8h14M7 8l-3 6a3 3 0 006 0L7 8zm10 0l-3 6a3 3 0 006 0l-3-6zM9 21h6"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
}

function ThemeToggle() {
  const { mode, cycle } = useTheme();
  const { t } = useI18n();
  const Icon = mode === 'light' ? Sun : mode === 'dark' ? Moon : Monitor;
  const label = t(
    mode === 'light' ? 'settings.themeLight' : mode === 'dark' ? 'settings.themeDark' : 'settings.themeSystem',
  );

  return (
    <button
      onClick={cycle}
      title={label}
      aria-label={label}
      className="grid h-9 w-9 place-items-center rounded text-muted hover:bg-raised hover:text-ink transition-colors"
    >
      <Icon className="h-[18px] w-[18px]" aria-hidden />
    </button>
  );
}

function ConnectionPill() {
  const { t } = useI18n();
  const [online, setOnline] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const check = () =>
      api
        .health()
        .then(() => !cancelled && setOnline(true))
        .catch(() => !cancelled && setOnline(false));

    check();
    const timer = setInterval(check, 30000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  if (online === null) return null;

  return (
    <Badge tone={online ? 'ok' : 'bad'} icon={online ? Wifi : WifiOff}>
      {t(online ? 'common.online' : 'common.offline')}
    </Badge>
  );
}

function NavItems({ onNavigate }) {
  const { t } = useI18n();
  const { hasRole } = useAuth();

  return NAV.filter((item) => hasRole(item.role)).map((item) => (
    <NavLink
      key={item.to}
      to={item.to}
      end={item.end}
      onClick={onNavigate}
      className={({ isActive }) =>
        clsx(
          'flex items-center gap-3 rounded px-3 py-2 text-sm font-medium transition-colors',
          isActive ? 'bg-brand-soft text-brand' : 'text-muted hover:bg-raised hover:text-ink',
        )
      }
    >
      <item.icon className="h-[18px] w-[18px] shrink-0" aria-hidden />
      {t(item.key)}
    </NavLink>
  ));
}

export default function AppShell() {
  const { t } = useI18n();
  const { user, signOut } = useAuth();
  const location = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Close the mobile drawer whenever the route changes.
  useEffect(() => setDrawerOpen(false), [location.pathname]);

  const sidebar = (
    <>
      <div className="flex items-center gap-3 px-5 h-16 border-b border-line shrink-0">
        <Emblem className="h-9 w-9" />
        <div className="min-w-0">
          <p className="text-[13px] font-semibold text-ink leading-tight truncate">{t('app.name')}</p>
          <p className="text-[11px] text-faint truncate">{t('app.subtitle')}</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto p-3">
        <NavItems onNavigate={() => setDrawerOpen(false)} />
      </nav>

      <div className="border-t border-line p-3 shrink-0">
        <div className="flex items-center gap-3 rounded px-3 py-2">
          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-brand-soft text-[13px] font-semibold text-brand">
            {(user?.full_name || '?').charAt(0).toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-medium text-ink">{user?.full_name}</p>
            <p className="truncate text-[11px] text-faint">{t(`role.${user?.role}`)}</p>
          </div>
        </div>
        <Button variant="ghost" size="sm" icon={LogOut} onClick={signOut} className="mt-1 w-full justify-start">
          {t('nav.signOut')}
        </Button>
      </div>
    </>
  );

  return (
    <div className="flex min-h-screen bg-canvas">
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex w-64 shrink-0 flex-col border-r border-line bg-surface sticky top-0 h-screen">
        {sidebar}
      </aside>

      {/* Mobile drawer */}
      {drawerOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-ink/40" onClick={() => setDrawerOpen(false)} aria-hidden />
          <aside className="relative flex h-full w-[17rem] flex-col bg-surface shadow-pop animate-fade-up">
            <button
              onClick={() => setDrawerOpen(false)}
              className="absolute right-3 top-4 rounded p-1.5 text-muted hover:bg-raised"
              aria-label={t('common.close')}
            >
              <X className="h-4 w-4" aria-hidden />
            </button>
            {sidebar}
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center gap-3 border-b border-line bg-surface/85 px-4 backdrop-blur-md sm:px-6">
          <button
            onClick={() => setDrawerOpen(true)}
            className="grid h-9 w-9 place-items-center rounded text-muted hover:bg-raised lg:hidden"
            aria-label="Open navigation"
          >
            <Menu className="h-5 w-5" aria-hidden />
          </button>

          <div className="flex items-center gap-2.5 lg:hidden">
            <Emblem className="h-8 w-8" />
            <span className="text-[13px] font-semibold text-ink">{t('app.name')}</span>
          </div>

          <div className="ml-auto flex items-center gap-2">
            <ConnectionPill />
            <ThemeToggle />
          </div>
        </header>

        {/* pb-20 keeps content clear of the mobile bottom bar */}
        <main className="flex-1 px-4 py-6 pb-24 sm:px-6 lg:px-8 lg:pb-8">
          <Outlet />
        </main>
      </div>

      {/* Mobile bottom navigation */}
      <nav
        className="fixed inset-x-0 bottom-0 z-40 flex border-t border-line bg-surface/95 backdrop-blur-md lg:hidden"
        style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
      >
        {MOBILE_NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              clsx(
                'flex flex-1 flex-col items-center gap-1 py-2.5 text-[10px] font-medium transition-colors',
                isActive ? 'text-brand' : 'text-faint',
              )
            }
          >
            <item.icon className="h-5 w-5" aria-hidden />
            {t(item.key)}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
