"use client";

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
 * Mobile (< md): TopBar + main + BottomNav (stacked). Same tree, same
 * `main` — only the chrome around it changes with the breakpoint.
 *
 * Everything ink — no ivory canvas, no max-w-7xl. Content uses the full
 * available width (sidebar-excluded on desktop, full width on mobile).
 */
export function DashboardLayout({ children }: { children: React.ReactNode }) {
  /*
   * ONE tree, not two (2026-09-10).
   *
   * This used to render a desktop shell and a mobile shell side by side and
   * let `hidden md:flex` / `md:hidden` pick one. Both stayed in the DOM, so
   * every dashboard page mounted TWICE: every effect, listener, toast and
   * poll ran twice, and every `id` inside a page existed twice (the settings
   * anchor rail resolved to the hidden copy on one of the two widths). The
   * shells only ever differed in chrome — sidebar vs bottom nav, and main's
   * padding — so the chrome is now responsive and `children` render once.
   *
   * Stacking: BottomNav stays inside the same wrapper as <main>, as before.
   * `.pq-dash-shell > *` gives each direct child `position: relative;
   * z-index: 1` (globals.css), so a fixed nav placed as a direct child would
   * lose `position: fixed`, and in its own wrapper it would paint over page
   * modals. Keep it here.
   */
  return (
    <div
      className="min-h-screen bg-[var(--pq-ink)] text-[var(--pq-ivory)] pq-dash-shell"
      data-pq-dash-shell
    >
      <div className="flex min-h-screen">
        {/* Sidebar rail — desktop / tablet only (≥ md) */}
        <aside
          className="hidden md:block sticky top-0 h-screen w-[240px] shrink-0 border-r border-[var(--pq-ivory-line)] bg-[var(--pq-ink)]"
        >
          <TerminalSidebar variant="rail" />
        </aside>

        {/* Content column — TopBar + main, at every width */}
        <div className="flex min-h-screen flex-1 flex-col min-w-0">
          <div data-pq-dash-topbar className="pq-dash-topbar">
            <TopBar />
          </div>
          {/* Mobile pb = bottom-nav (h-16 64px) + safe-area-bottom + 16px
              gutter so the last block clears the fixed nav (z-50) on notch
              devices. Desktop has no bottom nav, so it keeps py-8. */}
          <main
            id="main-content"
            className="flex-1 px-4 py-6 pb-[var(--pq-bottomnav-clearance)] md:px-10 md:py-8 md:pb-8"
          >
            {children}
          </main>
        </div>

        {/* Bottom nav — fixed, and hides itself at ≥ md (bottom-nav.tsx) */}
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
