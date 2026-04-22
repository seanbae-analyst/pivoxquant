"use client";

/**
 * TopBar — PivoxQuant editorial shell header.
 *
 * Hosts:
 *   - Search trigger (opens <SearchCommandMenu/> command palette via Cmd+K).
 *   - <NotificationDropdown/> — Bronze-accent bell.
 *   - <ProfileDropdown/> — Bronze-outline avatar with tier chip.
 *
 * Height 56px, Ivory background, single hairline at the bottom.
 */

import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { SearchCommandMenu, openSearchCommand } from "@/components/ui/search-command";
import { NotificationDropdown } from "@/components/ui/notification-dropdown";
import { ProfileDropdown } from "@/components/ui/profile-dropdown";

export function TopBar() {
  const [isMac, setIsMac] = useState(false);

  useEffect(() => {
    setIsMac(
      typeof navigator !== "undefined" && /mac/i.test(navigator.userAgent),
    );
  }, []);

  return (
    <>
      <header
        className="flex h-14 items-center justify-between gap-4 px-6"
        style={{
          background: "var(--pq-ivory)",
          borderBottom: "0.5px solid var(--pq-hairline)",
        }}
      >
        {/* ── Search trigger (looks like an input, opens palette) ── */}
        <button
          type="button"
          onClick={() => openSearchCommand()}
          aria-label="Search ticker or page"
          className="flex h-9 w-full max-w-[440px] items-center gap-3 rounded-full px-4 text-left transition-colors hover:bg-[rgba(139,111,71,0.06)]"
          style={{
            border: "0.5px solid var(--pq-hairline)",
            background: "transparent",
          }}
        >
          <Search className="h-[14px] w-[14px] shrink-0" style={{ color: "var(--pq-bronze)" }} />
          <span
            className="flex-1 text-sm italic"
            style={{
              fontFamily: "var(--font-serif), serif",
              color: "var(--pq-muted)",
            }}
          >
            Search ticker, page…
          </span>
          <kbd
            className="rounded px-1.5 py-0.5 font-mono text-[10px]"
            style={{
              border: "0.5px solid var(--pq-hairline)",
              color: "var(--pq-muted)",
              letterSpacing: "0.05em",
            }}
          >
            {isMac ? "⌘K" : "Ctrl+K"}
          </kbd>
        </button>

        {/* ── Right cluster ── */}
        <div className="flex items-center gap-1.5">
          <NotificationDropdown />
          <ProfileDropdown />
        </div>
      </header>

      {/* Global command palette (mounted once, controlled via openSearchCommand()) */}
      <SearchCommandMenu />
    </>
  );
}
