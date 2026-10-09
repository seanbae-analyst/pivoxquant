"use client";

/**
 * BottomNav — the phone tab bar.
 *
 * Rendered by <DashboardLayout/> below `md` (< 768px). Visual language
 * mirrors <TerminalSidebar/>: Vantablack ink ground, Ivory text, Bronze
 * accent on the active tab (top hairline + icon tint + label ink).
 *
 * 2026-09-20 — the bar became 거울 / 멈춤 / 기록 + 더보기 (the landing
 * promises exactly those three screens and the CEO could not find 기록).
 *
 * 2026-10-09 (CEO) — four tabs, no drawer: 거울 · 멈춤 · 기록 · 포트폴리오.
 * 포트폴리오 was the only thing in the 더보기 drawer anyone opened; a drawer
 * holding one screen is a website's hamburger, not an app's tab bar. 설정 and
 * 로그아웃 live in the app bar's avatar menu (profile-dropdown.tsx, which also
 * links /support). /settings and /support/* light no tab — they are reached
 * from the avatar, like an app's account screen.
 *
 * Native behaviour:
 *   - The tapped tab lights at once, not when the route commits.
 *   - Tapping the tab you are on scrolls that screen back to the top.
 *   - Press feedback (dim + icon press-in) is in globals.css
 *     ("Touch feedback"), keyed on [data-pq-bottom-nav].
 *
 * Accessibility:
 *   - `<nav aria-label>`; `aria-current="page"` on the shown route's tab.
 *   - 64px-tall targets, a quarter of the width each.
 *   - `safe-area-inset-bottom` honoured via `.pq-bottom-nav` (see
 *     globals.css PWA standalone block).
 */

import { useState } from "react";
import type { MouseEvent } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Briefcase, Contrast, Gavel, NotebookPen } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { SCROLL_TOP_EVENT } from "@/lib/scroll-top-event";

type Tab = {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Real sub-routes that still belong to this tab (exact paths). */
  subRoutes?: ReadonlyArray<string>;
};

// 거울 (Mirror) leads as the home; 멈춤 → 기록 → 거울 is the product loop;
// 포트폴리오 last — the one screen that is a ledger rather than the loop.
// Labels are literal (no locale dep) so a missing i18n key can never blank
// the bar on mobile.
export const PRIMARY_TABS: ReadonlyArray<Tab> = [
  { href: "/mirror", label: "거울", icon: Contrast },
  { href: "/pre-trade", label: "멈춤", icon: Gavel },
  { href: "/journal", label: "기록", icon: NotebookPen, subRoutes: ["/journal/import"] },
  { href: "/portfolio", label: "포트폴리오", icon: Briefcase },
];

/**
 * Whether `pathname` is one of the tab's own screens — the tab root or one of
 * its listed sub-routes, matched exactly. A prefix match would light 거울 on
 * the in-app 404 for /mirror/nope; an unknown path lights no tab.
 */
export function isRouteActive(
  pathname: string | null,
  href: string,
  subRoutes: ReadonlyArray<string> = [],
): boolean {
  if (!pathname) return false;
  const path = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  return path === href || subRoutes.includes(path);
}

function isPlainClick(e: MouseEvent): boolean {
  return !(e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0);
}

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
  );
}

export function BottomNav() {
  const pathname = usePathname();

  // A tab lights the moment it is tapped, not when the route commits (a cold
  // route can take a second on a phone). Remembered against the pathname it
  // was tapped on, so it expires by itself once the navigation lands — or if
  // the user ends up somewhere else.
  const [tapped, setTapped] = useState<{ href: string; from: string | null } | null>(null);
  const pendingHref = tapped && tapped.from === pathname ? tapped.href : null;
  const isLit = (tab: Tab) =>
    pendingHref ? pendingHref === tab.href : isRouteActive(pathname, tab.href, tab.subRoutes);

  function onTabClick(e: MouseEvent<HTMLAnchorElement>, href: string) {
    if (!isPlainClick(e)) return;
    if (pathname === href) {
      // Native tab bars: tapping the current tab scrolls it back to the top.
      e.preventDefault();
      window.scrollTo({ top: 0, behavior: prefersReducedMotion() ? "auto" : "smooth" });
      window.dispatchEvent(new Event(SCROLL_TOP_EVENT));
      return;
    }
    setTapped({ href, from: pathname });
  }

  return (
    <nav
      className="pq-bottom-nav fixed inset-x-0 bottom-0 z-50 md:hidden"
      aria-label="Primary mobile navigation"
      data-pq-bottom-nav
      data-pq-chrome
      style={{
        background: "var(--pq-ink)",
        borderTop: "0.5px solid var(--pq-ivory-line)",
        paddingBottom: "env(safe-area-inset-bottom, 0px)",
      }}
    >
      <ul className="flex h-16 items-stretch">
        {PRIMARY_TABS.map((tab) => (
          <BottomTab
            key={tab.href}
            tab={tab}
            active={isLit(tab)}
            current={isRouteActive(pathname, tab.href, tab.subRoutes)}
            onClick={(e) => onTabClick(e, tab.href)}
          />
        ))}
      </ul>
    </nav>
  );
}

// ─── Subcomponents ────────────────────────────────────────────────────────────

function BottomTab({
  tab,
  active,
  current,
  onClick,
}: {
  tab: Tab;
  /** Lit: the current route, or the tab just tapped while its route loads. */
  active: boolean;
  /** The route actually shown — what aria-current reports. */
  current: boolean;
  onClick: (e: MouseEvent<HTMLAnchorElement>) => void;
}) {
  const Icon = tab.icon;
  return (
    <li className="flex-1">
      <Link
        href={tab.href}
        onClick={onClick}
        aria-current={current ? "page" : undefined}
        data-lit={active ? "true" : undefined}
        className="group relative flex h-full w-full flex-col items-center justify-center gap-1"
      >
        <TopHairline active={active} />
        <Icon
          className="h-[18px] w-[18px] shrink-0"
          strokeWidth={1.5}
          style={{
            color: active ? "var(--pq-bronze)" : "rgba(245, 240, 232, 0.5)",
          }}
        />
        <span
          className="font-serif uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.14em",
            color: active ? "var(--pq-ivory)" : "rgba(245, 240, 232, 0.55)",
          }}
        >
          {tab.label}
        </span>
      </Link>
    </li>
  );
}

/** Bronze hairline sitting flush with the nav's top border. Visible only on
 *  the active tab — mirrors TerminalSidebar's left-edge bronze accent. */
function TopHairline({ active }: { active: boolean }) {
  return (
    <span
      aria-hidden="true"
      className="absolute inset-x-3 top-0 h-[2px]"
      style={{
        background: active ? "var(--pq-bronze)" : "transparent",
        transition:
          "background var(--motion-duration-fast) var(--motion-easing-emphasized)",
      }}
    />
  );
}
