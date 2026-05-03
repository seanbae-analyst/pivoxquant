"use client";

import { useEffect, useState } from "react";
import { TopBar } from "./top-bar";
import { TerminalSidebar } from "./terminal-sidebar";
import { BottomNav } from "./bottom-nav";

/**
 * Dashboard shell — full-screen Vantablack.
 *
 * Desktop (≥ md):
 *   ┌────────────────────────────────────────────────────────┐
 *   │  Sidebar rail (240px) │ TopBar (full width content col)│
 *   │                        ├────────────────────────────────┤
 *   │                        │   <main> flex-1 padded         │
 *   └────────────────────────────────────────────────────────┘
 *
 * Mobile (< md): TopBar + main + BottomNav (stacked).
 *
 * Everything ink — no ivory canvas, no max-w-7xl. Content uses the full
 * available width (sidebar-excluded on desktop, full width on mobile).
 */
export function DashboardLayout({ children }: { children: React.ReactNode }) {
  /*
   * Skip-link target — both desktop and mobile shells render simultaneously
   * (Tailwind `hidden md:flex` / `md:hidden` toggles `display`, the elements
   * remain in the DOM). To avoid duplicate `id="main-content"` we attach the
   * id to whichever <main> is currently visible based on viewport width.
   * SSR pre-hydration: we default to `desktop` so server output matches the
   * common case; the listener corrects post-mount. (WCAG 2.4.1 Level A.)
   */
  const [isDesktop, setIsDesktop] = useState(true);
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 768px)");
    const update = () => setIsDesktop(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);

  return (
    <div
      className="min-h-screen bg-[var(--pq-ink)] text-[var(--pq-ivory)] pq-dash-shell"
      data-pq-dash-shell
    >
      {/* ── Desktop + Tablet (≥ md) ── */}
      <div className="hidden md:flex md:min-h-screen">
        {/* Sidebar rail — sticky full-height column */}
        <aside
          className="sticky top-0 h-screen w-[240px] shrink-0 border-r border-[rgba(245,240,232,0.08)] bg-[var(--pq-ink)]"
        >
          <TerminalSidebar variant="rail" />
        </aside>

        {/* Right column — TopBar + scrollable main */}
        <div className="flex min-h-screen flex-1 flex-col min-w-0">
          <div data-pq-dash-topbar className="pq-dash-topbar">
            <TopBar />
          </div>
          <main {...(isDesktop ? { id: "main-content" } : {})} className="flex-1 px-8 md:px-10 py-8">{children}</main>
        </div>
      </div>

      {/* ── Mobile (< md) ── */}
      <div className="flex min-h-screen flex-col md:hidden">
        <div data-pq-dash-topbar className="pq-dash-topbar">
          <TopBar />
        </div>
        <main {...(!isDesktop ? { id: "main-content" } : {})} className="flex-1 px-4 py-6 pb-24">{children}</main>
        <BottomNav />
      </div>

      {/*
       * Global Cmd+K palette is mounted by <TopBar /> via
       * <SearchCommandMenu />. The previous terminal-CommandPalette here
       * registered a *second* document-level Cmd+K listener, so pressing
       * the shortcut opened both palettes stacked on top of each other.
       * Removed 2026-05-01; SearchCommandMenu is the single source of
       * truth (live /api/search + Pages + Recents).
       */}
    </div>
  );
}
