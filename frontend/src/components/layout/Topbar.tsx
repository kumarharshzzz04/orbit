// ORBIT Frontend - Topbar Component
// Top navigation with breadcrumbs, connection status, and mission context

import { NavLink, useLocation } from 'react-router-dom';
import {
  Wifi,
  Bell,
  Sun,
  Moon,
  ChevronDown,
  Zap,
  CheckCircle,
} from 'lucide-react';
import { useOrbitStore } from '@/stores/useOrbitStore';
import { Button } from '@/components/ui/Button';
import { useTheme } from '@/hooks/useTheme';

interface BreadcrumbItem {
  label: string;
  href?: string;
}

const ROUTE_LABELS: Record<string, string> = {
  '/': 'Overview',
  '/missions': 'Missions',
  '/missions/new': 'New Mission',
  '/research': 'Research',
  '/hypotheses': 'Hypotheses',
  '/hypotheses/new': 'New Hypothesis',
  '/experiments': 'Experiments',
  '/experiments/new': 'New Experiment',
  '/registry': 'Model Registry',
  '/live': 'Live Operations',
  '/settings': 'Settings',
};

export function Topbar() {
  const location = useLocation();
  const { activeMissionId, setActiveMissionId } = useOrbitStore();
  const { resolvedTheme, setTheme } = useTheme();

  // Generate breadcrumbs
  const breadcrumbs: BreadcrumbItem[] = [{ label: 'ORBIT', href: '/' }];

  const pathParts = location.pathname.split('/').filter(Boolean);
  let currentPath = '';

  pathParts.forEach((part, index) => {
    currentPath += `/${part}`;
    const isLast = index === pathParts.length - 1;

    const label = ROUTE_LABELS[currentPath] || part.replace(/-/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());

    breadcrumbs.push({
      label,
      href: isLast ? undefined : currentPath,
    });
  });

  return (
    <header className="sticky top-0 z-30 bg-orbit-bg-secondary/80 backdrop-blur-xl border-b border-orbit-border-primary">
      <div className="flex h-16 items-center justify-between px-6 gap-4">
        {/* Breadcrumbs */}
        <nav className="flex-1 flex items-center gap-2 overflow-x-auto" aria-label="Breadcrumb">
          <ol className="flex items-center gap-2 whitespace-nowrap">
            {breadcrumbs.map((item, index) => (
              <li key={item.href || item.label} className="flex items-center gap-2">
                {index > 0 && (
                  <ChevronDown className="h-4 w-4 text-orbit-text-tertiary flex-shrink-0" aria-hidden="true" />
                )}
                {item.href ? (
                  <NavLink
                    to={item.href}
                    className="text-sm font-medium text-orbit-text-secondary hover:text-orbit-text-primary transition-colors"
                  >
                    {item.label}
                  </NavLink>
                ) : (
                  <span className="text-sm font-medium text-orbit-text-primary">{item.label}</span>
                )}
              </li>
            ))}
          </ol>
        </nav>

        {/* Right side actions */}
        <div className="flex items-center gap-3 flex-shrink-0">
          {/* Connection Indicators */}
          <div className="hidden md:flex items-center gap-3">
            {/* Backend Status */}
            <div className="flex items-center gap-2 px-3 py-1.5 bg-orbit-bg-tertiary rounded-lg border border-orbit-border-primary">
              <CheckCircle className="h-4 w-4 text-orbit-accent-positive" aria-hidden="true" />
              <span className="text-xs font-medium text-orbit-text-secondary">API</span>
            </div>

            {/* WebSocket Status */}
            <div className="flex items-center gap-2 px-3 py-1.5 bg-orbit-bg-tertiary rounded-lg border border-orbit-border-primary">
              <Wifi className="h-4 w-4 text-orbit-accent-positive" aria-hidden="true" />
              <span className="text-xs font-medium text-orbit-text-secondary">WS</span>
            </div>

            {/* Mission Context */}
            {activeMissionId && (
              <div className="flex items-center gap-2 px-3 py-1.5 bg-orbit-accent-primary/10 rounded-lg border border-orbit-accent-primary/20">
                <Zap className="h-4 w-4 text-orbit-accent-primary" aria-hidden="true" />
                <span className="text-xs font-mono text-orbit-accent-primary">{activeMissionId}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setActiveMissionId(null)}
                  aria-label="Clear mission context"
                  className="text-orbit-accent-primary hover:text-orbit-text-primary p-1"
                >
                  <ChevronDown className="h-3 w-3" />
                </Button>
              </div>
            )}
          </div>

          {/* Theme Toggle */}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
            aria-label={resolvedTheme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            className="md:hidden"
          >
            {resolvedTheme === 'dark' ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </Button>

          {/* Notifications */}
          <Button variant="ghost" size="sm" aria-label="Notifications">
            <Bell className="h-5 w-5" />
          </Button>

          {/* Theme Toggle (Desktop) */}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
            aria-label={resolvedTheme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            className="hidden md:flex"
          >
            {resolvedTheme === 'dark' ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </Button>
        </div>
      </div>
    </header>
  );
}