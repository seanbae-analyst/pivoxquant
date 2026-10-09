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

import { useEffect, useRef } from "react";
import { usePathname, useRouter } from "next/navigation";
import { ChevronLeft } from "lucide-react";

import { NotificationDropdown } from "@/components/ui/notification-dropdown";
import { ProfileDropdown } from "@/components/ui/profile-dropdown";
import {
  SETTINGS_PANES,
  closePane,
  useSettingsPane,
  type SettingsPane,
} from "@/components/settings/v2/settings-phone-nav";

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

/**
 * Sub-screens get an iOS-style back chevron + their own title in the phone
 * app bar (2026-10-09), instead of a "← 돌아가기" link inside the content.
 * `parent` is where back goes; `parentLabel` names it for screen readers.
 * Settings panes are not routes — they live in `?s=` (settings-phone-nav),
 * so they come in as `pane` and close through closePane().
 */
export type SubScreen = {
  title: string;
  parent: string;
  parentLabel: string;
  /** Settings pane: back closes the pane (history-aware), not a route push. */
  pane?: SettingsPane;
};

export function subScreen(pathname: string | null, pane: SettingsPane | null): SubScreen | null {
  if (!pathname) return null;
  if (pathname === "/journal/import" || pathname.startsWith("/journal/import/")) {
    return { title: "체결 가져오기", parent: "/journal", parentLabel: "기록" };
  }
  if (/^\/support\/inbox\/[^/]+$/.test(pathname)) {
    return { title: "문의 내용", parent: "/support/inbox", parentLabel: "내 문의함" };
  }
  if (pathname === "/settings" && pane) {
    const title = SETTINGS_PANES.find((p) => p.id === pane)?.title;
    if (title) return { title, parent: "/settings", parentLabel: "설정", pane };
  }
  return null;
}

export function TopBar() {
  const pathname = usePathname();
  const router = useRouter();
  const pane = useSettingsPane();
  const sub = subScreen(pathname, pane);
  const title = sub ? sub.title : screenTitle(pathname);

  // The route before this one, so back can POP to the parent (native) when
  // the user came from it, and only push the parent on a deep link.
  const prevPath = useRef<string | null>(null);
  const currentPath = useRef<string | null>(pathname);
  useEffect(() => {
    if (currentPath.current !== pathname) {
      prevPath.current = currentPath.current;
      currentPath.current = pathname;
    }
  }, [pathname]);

  const goBack = () => {
    if (!sub) return;
    if (sub.pane) {
      closePane();
      return;
    }
    if (prevPath.current === sub.parent) router.back();
    else router.push(sub.parent);
  };

  return (
    <header
      className="relative z-50 flex h-14 items-center justify-end gap-4 px-4 md:px-6"
      data-pq-chrome
      style={{
        background: "var(--pq-ink)",
        borderBottom: "0.5px solid var(--pq-ivory-line)",
      }}
    >
      {sub && (
        <button
          type="button"
          onClick={goBack}
          aria-label={`${sub.parentLabel}(으)로 돌아가기`}
          className="-ml-3 -mr-3 flex h-12 w-12 shrink-0 items-center justify-center text-[var(--pq-bronze-light)] md:hidden"
          data-testid="topbar-back"
        >
          <ChevronLeft className="h-6 w-6" strokeWidth={1.5} aria-hidden />
        </button>
      )}
      {title && (
        <div
          className="mr-auto min-w-0 truncate font-serif text-[19px] leading-none text-[var(--pq-ivory)] md:hidden"
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
