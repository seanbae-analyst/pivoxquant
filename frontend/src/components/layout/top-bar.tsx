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

import { usePathname } from "next/navigation";

import { NotificationDropdown } from "@/components/ui/notification-dropdown";
import { ProfileDropdown } from "@/components/ui/profile-dropdown";

/**
 * Screen title for the phone app bar (2026-10-07, CEO "너무 웹사이트야").
 * On a phone the bar used to hold only the bell and the avatar, so nothing
 * said which screen you were on; the page's own editorial headline did that
 * job half a screen down. An app names the screen in its bar. Desktop keeps
 * the sidebar, which already marks the active screen, so the title is
 * phone-only. Literal labels, like bottom-nav.tsx, so a missing i18n key can
 * never blank the bar.
 */
const SCREEN_TITLES: ReadonlyArray<readonly [string, string]> = [
  ["/mirror", "거울"],
  ["/pre-trade", "멈춤"],
  ["/journal", "기록"],
  ["/portfolio", "포트폴리오"],
  ["/settings", "설정"],
  ["/support", "문의"],
];

export function screenTitle(pathname: string | null): string | null {
  if (!pathname) return null;
  for (const [prefix, title] of SCREEN_TITLES) {
    if (pathname === prefix || pathname.startsWith(prefix + "/")) return title;
  }
  return null;
}

export function TopBar() {
  const title = screenTitle(usePathname());
  return (
    <header
      className="relative z-50 flex h-14 items-center justify-end gap-4 px-4 md:px-6"
      style={{
        background: "var(--pq-ink)",
        borderBottom: "0.5px solid var(--pq-ivory-line)",
      }}
    >
      {title && (
        <div
          className="mr-auto font-serif text-[19px] leading-none text-[var(--pq-ivory)] md:hidden"
          data-testid="topbar-title"
        >
          {title}
        </div>
      )}
      <div className="flex items-center gap-2 md:gap-1.5">
        <NotificationDropdown />
        <ProfileDropdown />
      </div>
    </header>
  );
}
