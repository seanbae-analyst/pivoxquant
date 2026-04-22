"use client";

import { Sidebar } from "./sidebar";
import { TopBar } from "./top-bar";
import { BottomNav } from "./bottom-nav";

export function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="pq-dash-shell min-h-screen"
      style={{ backgroundColor: "var(--pq-ivory)" }}
    >
      {/* Desktop: Vantablack sidebar left + Ivory content right */}
      <div className="hidden md:flex">
        <Sidebar />
        <div className="flex min-h-screen flex-1 flex-col">
          <TopBar />
          <main className="flex-1 px-6 md:px-10 py-8">{children}</main>
        </div>
      </div>

      {/* Mobile: Ivory content + bottom nav */}
      <div className="flex min-h-screen flex-col md:hidden">
        <TopBar />
        <main className="flex-1 px-4 py-6 pb-24">{children}</main>
        <BottomNav />
      </div>
    </div>
  );
}
