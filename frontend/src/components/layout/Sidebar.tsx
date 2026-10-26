// ORBIT Frontend - Sidebar Component
// Collapsible navigation sidebar with mission context

import { NavLink, useLocation } from 'react-router-dom';
import { useState } from 'react';
import {
  LayoutDashboard,
  Target,
  BookOpen,
  Lightbulb,
  FlaskConical,
  Database,
  Activity,
  Settings,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { useOrbitStore } from '@/stores/useOrbitStore';
import { Button } from '@/components/ui/Button';

interface NavItem {
  path: string;
  label: string;
  icon: React.ReactNode;
  badge?: string | number;
  disabled?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { path: '/', label: 'Overview', icon: <LayoutDashboard className="h-5 w-5" /> },
  { path: '/missions', label: 'Missions', icon: <Target className="h-5 w-5" /> },
  { path: '/research', label: 'Research', icon: <BookOpen className="h-5 w-5" /> },
  { path: '/hypotheses', label: 'Hypotheses', icon: <Lightbulb className="h-5 w-5" /> },
  { path: '/experiments', label: 'Experiments', icon: <FlaskConical className="h-5 w-5" /> },
  { path: '/registry', label: 'Model Registry', icon: <Database className="h-5 w-5" /> },
  { path: '/live', label: 'Live Operations', icon: <Activity className="h-5 w-5" /> },
  { path: '/settings', label: 'Settings', icon: <Settings className="h-5 w-5" /> },
];

export function Sidebar() {
  const location = useLocation();
  const { sidebarCollapsed, sidebarCompact, setSidebarCollapsed } = useOrbitStore();
  const [hovered, setHovered] = useState(false);

  const effectiveCollapsed = sidebarCollapsed;

  return (
    <aside
      className={`fixed left-0 top-0 z-40 h-full bg-orbit-bg-secondary border-r border-orbit-border-primary transition-all duration-300 ease-in-out flex flex-col
        ${effectiveCollapsed ? 'w-16' : 'w-64'}
        ${sidebarCompact ? 'w-20' : ''}`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Logo / Brand */}
      <div className="flex items-center justify-between h-16 px-4 border-b border-orbit-border-primary">
        {!effectiveCollapsed && (
          <NavLink to="/" className="flex items-center gap-3" aria-label="ORBIT Home">
            <svg className="h-8 w-8 text-orbit-accent-primary" viewBox="0 0 32 32" fill="none" aria-hidden="true">
              <circle cx="16" cy="16" r="12" stroke="currentColor" strokeWidth="2" fill="none" opacity="0.3" />
              <circle cx="16" cy="16" r="8" stroke="currentColor" strokeWidth="2.5" fill="none" />
              <ellipse cx="16" cy="16" rx="14" ry="4" stroke="currentColor" strokeWidth="1.5" fill="none" transform="rotate(-20 16 16)" opacity="0.5" />
              <ellipse cx="16" cy="16" rx="14" ry="4" stroke="currentColor" strokeWidth="1.5" fill="none" transform="rotate(20 16 16)" opacity="0.5" />
              <circle cx="16" cy="16" r="3" fill="currentColor" />
            </svg>
            <span className="font-semibold text-lg text-orbit-text-primary">ORBIT</span>
          </NavLink>
        )}
        {effectiveCollapsed && (
          <NavLink to="/" className="flex items-center justify-center" aria-label="ORBIT Home">
            <svg className="h-8 w-8 text-orbit-accent-primary" viewBox="0 0 32 32" fill="none" aria-hidden="true">
              <circle cx="16" cy="16" r="12" stroke="currentColor" strokeWidth="2" fill="none" opacity="0.3" />
              <circle cx="16" cy="16" r="8" stroke="currentColor" strokeWidth="2.5" fill="none" />
              <ellipse cx="16" cy="16" rx="14" ry="4" stroke="currentColor" strokeWidth="1.5" fill="none" transform="rotate(-20 16 16)" opacity="0.5" />
              <ellipse cx="16" cy="16" rx="14" ry="4" stroke="currentColor" strokeWidth="1.5" fill="none" transform="rotate(20 16 16)" opacity="0.5" />
              <circle cx="16" cy="16" r="3" fill="currentColor" />
            </svg>
          </NavLink>
        )}

        {!sidebarCollapsed && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className="text-orbit-text-tertiary hover:text-orbit-text-primary"
          >
            {sidebarCollapsed ? <ChevronRight className="h-5 w-5" /> : <ChevronLeft className="h-5 w-5" />}
          </Button>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto p-3 space-y-1" aria-label="Main navigation">
        {NAV_ITEMS.map((item) => {
          const isActive = location.pathname === item.path || (item.path !== '/' && location.pathname.startsWith(item.path + '/'));
          const isDisabled = item.disabled;

          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive: active }) => `
                flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors duration-150
                ${isDisabled ? 'opacity-50 pointer-events-none' : ''}
                ${active
                  ? 'bg-orbit-accent-primary/10 text-orbit-accent-primary border border-orbit-accent-primary/20'
                  : 'text-orbit-text-secondary hover:text-orbit-text-primary hover:bg-orbit-bg-tertiary'}
                ${effectiveCollapsed ? 'justify-center' : ''}
              `}
              title={effectiveCollapsed && !hovered ? item.label : undefined}
              aria-current={isActive ? 'page' : undefined}
              aria-disabled={isDisabled}
              tabIndex={isDisabled ? -1 : undefined}
            >
              <span className="flex-shrink-0" aria-hidden="true">{item.icon}</span>
              {!effectiveCollapsed && <span className="font-medium truncate">{item.label}</span>}
              {item.badge && !effectiveCollapsed && (
                <span className="ml-auto px-2 py-0.5 text-xs font-medium bg-orbit-accent-primary/20 text-orbit-accent-primary rounded-full">
                  {item.badge}
                </span>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Connection Status */}
      <div className="p-3 border-t border-orbit-border-primary">
        {!effectiveCollapsed ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-xs text-orbit-text-tertiary">
              <span className="flex items-center gap-1.5">
                <span className="status-dot connected" aria-hidden="true" />
                <span>Backend Connected</span>
              </span>
            </div>
            <div className="flex items-center gap-2 text-xs text-orbit-text-tertiary">
              <span className="flex items-center gap-1.5">
                <span className="status-dot connected" aria-hidden="true" />
                <span>WebSocket Ready</span>
              </span>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <div className="flex items-center gap-1.5" title="Backend Connected">
              <span className="status-dot connected" aria-hidden="true" />
            </div>
            <div className="flex items-center gap-1.5" title="WebSocket Ready">
              <span className="status-dot connected" aria-hidden="true" />
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}