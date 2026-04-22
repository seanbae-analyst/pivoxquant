"use client";

import { TopBar } from "./top-bar";
import { BottomNav } from "./bottom-nav";

/**
 * Dashboard shell — ivory canvas only.
 * Each page renders its own Vantablack terminal card (with its own inner
 * sidebar) inside the canvas, matching the landing-preview visual.
 * The legacy outer <Sidebar /> was removed to avoid a double-sidebar on /home.
 */
export function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="min-h-screen"
      style={{ backgroundColor: "var(--pq-ivory)" }}
    >
      {/* Desktop + Tablet */}
      <div className="hidden min-h-screen md:flex md:flex-col">
        <TopBar />
        <main
          className="flex-1"
          style={{ backgroundColor: "var(--pq-ivory)" }}
        >
          <div className="mx-auto max-w-7xl px-6 md:px-8 py-8">
            {children}
          </div>
        </main>
      </div>

      {/* Mobile */}
      <div className="flex min-h-screen flex-col md:hidden">
        <TopBar />
        <main
          className="flex-1 pb-24"
          style={{ backgroundColor: "var(--pq-ivory)" }}
        >
          <div className="px-4 py-6">{children}</div>
        </main>
        <BottomNav />
      </div>
    </div>
  );
}
