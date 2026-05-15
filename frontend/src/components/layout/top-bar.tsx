"use client";

/**
 * TopBar — PivoxQuant editorial shell header, Vantablack variant.
 *
 * Hosts:
 *   - Search trigger (opens <SearchCommandMenu/> via Cmd+K).
 *   - <NotificationDropdown/> — Bronze-accent bell.
 *   - <ProfileDropdown/> — Bronze-outline avatar with tier chip.
 *
 * Height 56px, ink background to blend seamlessly into the new
 * full-screen dashboard shell. Single ivory hairline at the bottom.
 */

import { useSyncExternalStore } from "react";
import { Search } from "lucide-react";
import { SearchCommandMenu, openSearchCommand } from "@/components/ui/search-command";
import { NotificationDropdown } from "@/components/ui/notification-dropdown";
import { ProfileDropdown } from "@/components/ui/profile-dropdown";

// UA detection is a static client-only fact; no real subscription.
const noopSubscribe = () => () => {};
const getIsMacSnapshot = (): boolean => {
  if (typeof navigator === "undefined") return false;
  return /mac/i.test(navigator.userAgent);
};
const getIsMacServerSnapshot = () => false;

export function TopBar() {
  const isMac = useSyncExternalStore(
    noopSubscribe,
    getIsMacSnapshot,
    getIsMacServerSnapshot,
  );

  return (
    <>
      <header
        className="relative z-50 flex h-14 items-center justify-between gap-4 px-4 md:px-6"
        style={{
          background: "var(--pq-ink)",
          borderBottom: "0.5px solid var(--pq-ivory-line)",
        }}
      >
        {/* ── Search trigger (opens command palette) ──
            FINDING-020: rounded-full → rounded (4px). §0 forbids pill/full
            radius in the editorial tone; only the avatar stays circular. */}
        <button
          type="button"
          onClick={() => openSearchCommand()}
          aria-label="Find a ticker, an artifact, or a page"
          className="flex h-9 w-full max-w-[440px] items-center gap-3 rounded px-4 text-left transition-colors hover:bg-[rgba(139,111,71,0.08)]"
          style={{
            border: "0.5px solid rgba(245, 240, 232, 0.12)",
            background: "rgba(255, 255, 255, 0.02)",
          }}
        >
          <Search
            className="h-[14px] w-[14px] shrink-0"
            style={{ color: "var(--pq-bronze)" }}
          />
          {/* FINDING-039: brand-voice placeholder, not generic "Search …". */}
          <span
            className="flex-1 text-sm italic font-serif"
            style={{
              color: "rgba(245, 240, 232, 0.45)",
            }}
          >
            Find a ticker, an artifact, a page…
          </span>
          <kbd
            className="hidden md:inline-flex rounded px-1.5 py-0.5 font-mono text-pq-eyebrow"
            style={{
              border: "0.5px solid rgba(245, 240, 232, 0.15)",
              color: "rgba(245, 240, 232, 0.55)",
              letterSpacing: "0.05em",
            }}
          >
            {isMac ? "⌘K" : "Ctrl+K"}
          </kbd>
        </button>

        {/* ── Right cluster ── */}
        <div className="flex items-center gap-2 md:gap-1.5">
          <NotificationDropdown />
          <ProfileDropdown />
        </div>
      </header>

      {/* Global command palette — mounted once, controlled by openSearchCommand() */}
      <SearchCommandMenu />
    </>
  );
}
