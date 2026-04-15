"use client";

import { Sidebar } from "./sidebar";
import { TopBar } from "./top-bar";
import { BottomNav } from "./bottom-nav";

export function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[#fafafa]">
      {/* Desktop: sidebar left + content right */}
      <div className="hidden md:flex">
        <Sidebar />
        <div className="flex min-h-screen flex-1 flex-col">
          <TopBar />
          <main className="flex-1 p-6">{children}</main>
        </div>
      </div>

      {/* Mobile: content + bottom nav */}
      <div className="flex min-h-screen flex-col md:hidden">
        <TopBar />
        <main className="flex-1 p-4 pb-20">{children}</main>
        <BottomNav />
      </div>
    </div>
  );
}
