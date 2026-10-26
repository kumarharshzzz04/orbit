// ORBIT Frontend - App Shell
// Main application layout with sidebar, topbar, and content area

import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';
import { useOrbitStore } from '@/stores/useOrbitStore';

export function AppShell() {
  const { sidebarCollapsed, sidebarCompact } = useOrbitStore();

  const isCollapsed = sidebarCollapsed || sidebarCompact;

  return (
    <div className="min-h-screen bg-orbit-bg-primary flex">
      {/* Sidebar */}
      <Sidebar />

      {/* Main Content */}
      <div
        className={`flex-1 flex flex-col transition-all duration-300 ease-in-out
          ${isCollapsed ? 'lg:pl-16' : 'lg:pl-64'}`}
      >
        {/* Topbar */}
        <Topbar />

        {/* Page Content */}
        <main className="flex-1 p-6 lg:p-8 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}