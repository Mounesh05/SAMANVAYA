import React from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

export function AppShell() {
  return (
    <div className="app-shell">
      {/* Dynamic Role-Aware Sidebar */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="app-shell-content">
        <TopBar />
        <main className="app-main">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
