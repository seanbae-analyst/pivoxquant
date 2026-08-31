"use client";

/**
 * TopBar — PivoxQuant editorial shell header, Vantablack variant.
 *
 * Hosts:
 *   - <NotificationDropdown/> — Bronze-accent bell.
 *   - <ProfileDropdown/> — Bronze-outline avatar with tier chip.
 *
 * The Cmd+K palette that used to lead this bar is gone with the surfaces it
 * searched: its stock results only ever routed to /detail/[ticker], and its
 * page list is now shorter than the sidebar it duplicated.
 *
 * Height 56px, ink background to blend seamlessly into the new
 * full-screen dashboard shell. Single ivory hairline at the bottom.
 */

import { NotificationDropdown } from "@/components/ui/notification-dropdown";
import { ProfileDropdown } from "@/components/ui/profile-dropdown";

export function TopBar() {
  return (
    <header
      className="relative z-50 flex h-14 items-center justify-end gap-4 px-4 md:px-6"
      style={{
        background: "var(--pq-ink)",
        borderBottom: "0.5px solid var(--pq-ivory-line)",
      }}
    >
      <div className="flex items-center gap-2 md:gap-1.5">
        <NotificationDropdown />
        <ProfileDropdown />
      </div>
    </header>
  );
}
