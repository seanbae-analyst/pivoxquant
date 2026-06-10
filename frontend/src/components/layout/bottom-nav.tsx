"use client";

/**
 * BottomNav — Dossier editorial bottom tab bar, mobile only.
 *
 * Rendered by <DashboardLayout/> below `md` (< 768px). Visual language
 * mirrors <TerminalSidebar/>: Vantablack ink ground, Ivory text, Bronze
 * accent on the active tab (top hairline + icon tint + label ink).
 *
 * Layout: 5 primary tabs (Home / Portfolio / Brief / Signals / More).
 * The fifth opens a full drawer (ModalShell, slides from bottom) that
 * mirrors the desktop sidebar's 4-group IA — Artifacts / Portfolio /
 * Research / System — plus a Bronze-accent Sign Out at the foot.
 *
 * Accessibility:
 *   - `role="navigation"` + `aria-label`.
 *   - 44×44 min touch target per tab.
 *   - `aria-current="page"` on the active route.
 *   - `safe-area-inset-bottom` honoured via `.pq-bottom-nav` (see
 *     globals.css PWA standalone block).
 */

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Home as HomeIcon,
  Activity,
  Briefcase,
  Zap,
  MoreHorizontal,
  X,
  Eye,
  Compass,
  Shield,
  MessageSquare,
  BookHeart,
  NotebookPen,
  FileText,
  Bell,
  Settings as SettingsIcon,
  LogOut,
  Sparkles,
  UserCircle,
  Gavel,
  Sprout,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { ModalShell } from "@/components/ui/modal-shell";
import { useAuth } from "@/lib/auth";

type Tab = {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Render a small "Premium Plus" bronze seal next to the label. */
  premiumPlus?: boolean;
  /**
   * If true, the item is excluded from rendering but kept in the array
   * so the underlying route (e.g. /watchlist) continues to resolve when
   * users hit it via deep link, and route→active-state mapping stays
   * intact. 2026-04-27 per CEO: hide Morning Brief / Watchlist / Market
   * / Discover / AI Chat from sidebar + drawer (pages preserved).
   */
  hidden?: boolean;
};

type DrawerGroup = {
  /** Uppercase serif label shown above the group. */
  label: string;
  items: Tab[];
};

// Primary bottom-bar tabs — Home / Portfolio / Reports / Signals.
// Labels are literal (no locale dep) so a missing i18n key can never
// blank the bar on mobile.
//
// 2026-04-27 per CEO: Morning Brief replaced with Reports (Artifacts
// group sibling) on the primary bar so the mobile shell still has 4
// primary destinations after hiding Morning Brief.
// 2026-04-29: Morning Brief deep link fully removed (backend deprecated).
const PRIMARY_TABS: Tab[] = [
  { href: "/home", label: "Home", icon: HomeIcon },
  { href: "/portfolio", label: "Portfolio", icon: Briefcase },
  { href: "/reports", label: "Reports", icon: FileText },
  { href: "/signals", label: "Signals", icon: Zap },
];

// Drawer — mirrors the desktop sidebar's 4-group IA exactly
// (2026-06-10 record-as-spine reorg, CEO GO on
// docs/strategy/record-as-spine_2026-06-09.md §4.1): Record / Artifacts /
// Observe / System. Home is excluded from the drawer (it's already a
// primary tab); Reports and Signals are kept in their canonical groups so
// the user's mental map matches the desktop sidebar even though those two
// appear up in the primary bar as well.
const DRAWER_GROUPS: DrawerGroup[] = [
  {
    // 기록 — 척추 본체. Previously buried in "System" next to Settings.
    label: "Record",
    items: [
      // /journal — the user's own pre-trade decision-reflection feed
      // (read-only) + Behavior Mirrors.
      { href: "/journal", label: "Journal", icon: NotebookPen },
      // 2026-06-10: Pre-Trade RESTORED (removed 2026-05-21 as redundant
      // with the inline modal) — standalone deposition entry point.
      { href: "/pre-trade", label: "Pre-Trade", icon: Gavel },
      // Habit/reflection routine tracker. "Routine" label avoids §101
      // asset-growth language (see terminal-sidebar note).
      { href: "/growth", label: "Routine", icon: Sprout },
    ],
  },
  {
    label: "Artifacts",
    items: [
      // Morning Brief item REMOVED 2026-04-29 — backend deprecated.
      { href: "/reports", label: "Reports", icon: FileText },
    ],
  },
  {
    // 관측 — renamed from Research; absorbs the old Portfolio group.
    label: "Observe",
    items: [
      { href: "/portfolio", label: "Portfolio", icon: Briefcase },
      { href: "/signals", label: "Signals", icon: Zap },
      { href: "/risk", label: "Risk Board", icon: Shield },
      // REMOVED 2026-04-27 per CEO + legal: autotrade nav (투자일임업 회피).
      { href: "/ai", label: "AI Analysis", icon: Sparkles },
      { href: "/watchlist", label: "Watchlist", icon: Eye, hidden: true },
      { href: "/market", label: "Market", icon: Activity, hidden: true },
      { href: "/discover", label: "Discover", icon: Compass, hidden: true },
      { href: "/ai-chat", label: "AI Chat", icon: MessageSquare, hidden: true },
    ],
  },
  {
    label: "System",
    items: [
      { href: "/alerts", label: "Alerts", icon: Bell },
      // Journal Companion — Closed Beta, Premium Plus / Founding
      // Lifetime only. Entitlement enforcement lives on the page.
      { href: "/companion", label: "Companion", icon: BookHeart, premiumPlus: true },
      { href: "/profile", label: "Profile · Persona", icon: UserCircle },
      { href: "/settings", label: "Settings", icon: SettingsIcon },
    ],
  },
];

const ALL_DRAWER_HREFS: string[] = DRAWER_GROUPS.flatMap((g) => g.items.map((it) => it.href));

function isRouteActive(pathname: string | null, href: string): boolean {
  if (!pathname) return false;
  return pathname === href || pathname.startsWith(href + "/");
}

export function BottomNav() {
  const pathname = usePathname();
  const router = useRouter();
  const { logout } = useAuth();
  const [drawerOpen, setDrawerOpen] = useState(false);

  // "More" is active whenever the current path matches a drawer-only
  // route (one not already in the primary bar).
  const primaryHrefs = new Set(PRIMARY_TABS.map((t) => t.href));
  const moreActive = ALL_DRAWER_HREFS.some(
    (href) => !primaryHrefs.has(href) && isRouteActive(pathname, href),
  );

  async function handleSignOut() {
    setDrawerOpen(false);
    try {
      await logout();
    } finally {
      router.push("/");
    }
  }

  return (
    <>
      <nav
        className="pq-bottom-nav fixed inset-x-0 bottom-0 z-50 md:hidden"
        aria-label="Primary mobile navigation"
        data-pq-bottom-nav
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
              active={isRouteActive(pathname, tab.href)}
            />
          ))}
          <li className="flex-1">
            <button
              type="button"
              onClick={() => setDrawerOpen(true)}
              aria-label="Open navigation menu"
              aria-expanded={drawerOpen}
              aria-haspopup="dialog"
              className="group relative flex h-full w-full flex-col items-center justify-center gap-1"
            >
              <TopHairline active={moreActive || drawerOpen} />
              <MoreHorizontal
                className="h-[18px] w-[18px] shrink-0"
                strokeWidth={1.5}
                style={{
                  color:
                    moreActive || drawerOpen
                      ? "var(--pq-bronze)"
                      : "rgba(245, 240, 232, 0.5)",
                }}
              />
              <span
                className="font-serif uppercase"
                style={{
                  fontSize: "var(--pq-text-eyebrow)",
                  letterSpacing: "0.14em",
                  color:
                    moreActive || drawerOpen
                      ? "var(--pq-ivory)"
                      : "rgba(245, 240, 232, 0.55)",
                }}
              >
                More
              </span>
            </button>
          </li>
        </ul>
      </nav>

      {drawerOpen && (
        <ModalShell
          onClose={() => setDrawerOpen(false)}
          ariaLabel="Navigation menu"
          className="!items-end"
        >
          <div
            className="w-full rounded-t-[2px]"
            style={{
              background: "var(--pq-ink)",
              borderTop: "0.5px solid rgba(245, 240, 232, 0.12)",
              paddingBottom: "max(16px, env(safe-area-inset-bottom))",
            }}
          >
            {/* Drawer header */}
            <div
              className="flex items-center justify-between px-5 py-4"
              style={{
                borderBottom: "0.5px solid var(--pq-ivory-line)",
              }}
            >
              <span
                className="font-serif uppercase"
                style={{
                  fontSize: "var(--pq-text-eyebrow)",
                  letterSpacing: "0.24em",
                  color: "var(--pq-ivory)",
                }}
              >
                Menu
              </span>
              <button
                type="button"
                onClick={() => setDrawerOpen(false)}
                aria-label="Close menu"
                className="flex h-11 w-11 items-center justify-center rounded-sm transition-colors hover:bg-[rgba(247,245,239,0.06)]"
              >
                <X
                  className="h-4 w-4"
                  strokeWidth={1.5}
                  style={{ color: "rgba(245, 240, 232, 0.6)" }}
                />
              </button>
            </div>

            {/* Drawer body — 4-group IA mirroring the desktop sidebar */}
            <div
              className="max-h-[65vh] overflow-y-auto px-2 py-2"
              role="list"
            >
              {DRAWER_GROUPS.map((group) => (
                <DrawerGroupSection
                  key={group.label}
                  group={group}
                  pathname={pathname}
                  onNavigate={() => setDrawerOpen(false)}
                />
              ))}
            </div>

            {/* Sign out — Bronze-accent, hairline divider above */}
            <div
              className="px-2 pt-2"
              style={{
                borderTop: "0.5px solid var(--pq-ivory-line)",
              }}
            >
              <button
                type="button"
                onClick={handleSignOut}
                className="flex min-h-[44px] w-full items-center gap-3 rounded-sm font-serif uppercase transition-colors hover:bg-[rgba(184,149,106,0.08)]"
                style={{
                  padding: "13px 14px",
                  fontSize: "var(--pq-text-body)",
                  letterSpacing: "0.2em",
                  color: "var(--pq-bronze)",
                  borderLeft: "3px solid transparent",
                }}
              >
                <LogOut
                  className="h-[15px] w-[15px] shrink-0"
                  strokeWidth={1.5}
                  style={{ color: "var(--pq-bronze)" }}
                />
                Sign out
              </button>
            </div>
          </div>
        </ModalShell>
      )}
    </>
  );
}

// ─── Subcomponents ────────────────────────────────────────────────────────────

function DrawerGroupSection({
  group,
  pathname,
  onNavigate,
}: {
  group: DrawerGroup;
  pathname: string | null;
  onNavigate: () => void;
}) {
  return (
    <div className="mb-1">
      {/* Group header — bronze tint label + hairline divider */}
      <div className="px-3 mt-4 mb-1.5" aria-hidden="true">
        <span
          className="font-serif uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.22em",
            color: "rgba(184, 149, 106, 0.55)",
            display: "block",
          }}
        >
          {group.label}
        </span>
        <div
          className="mt-1 h-px"
          style={{ backgroundColor: "var(--pq-ivory-line)" }}
        />
      </div>

      <ul role="list">
        {group.items.filter((it) => !it.hidden).map((item) => {
          const active = isRouteActive(pathname, item.href);
          const Icon = item.icon;
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
                className="flex min-h-[44px] items-center gap-3 rounded-sm font-serif uppercase transition-colors"
                style={{
                  padding: "13px 14px",
                  fontSize: "var(--pq-text-body)",
                  letterSpacing: "0.2em",
                  color: active
                    ? "var(--pq-ivory)"
                    : "rgba(245, 240, 232, 0.62)",
                  backgroundColor: active
                    ? "rgba(247, 245, 239, 0.06)"
                    : "transparent",
                  borderLeft: active
                    ? "3px solid var(--pq-bronze)"
                    : "3px solid transparent",
                }}
              >
                <Icon
                  className="h-[15px] w-[15px] shrink-0"
                  strokeWidth={1.5}
                  style={{
                    color: active
                      ? "var(--pq-bronze)"
                      : "rgba(245, 240, 232, 0.55)",
                  }}
                />
                <span className="flex-1">{item.label}</span>
                {item.premiumPlus && (
                  <span
                    aria-label="Premium Plus · Closed Beta"
                    className="font-mono uppercase"
                    style={{
                      fontSize: "var(--pq-text-eyebrow)",
                      letterSpacing: "0.2em",
                      padding: "2px 6px",
                      borderRadius: 1,
                      background: "rgba(184, 149, 106, 0.12)",
                      border: "0.5px solid rgba(184, 149, 106, 0.4)",
                      color: "var(--pq-bronze)",
                    }}
                  >
                    Plus
                  </span>
                )}
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function BottomTab({ tab, active }: { tab: Tab; active: boolean }) {
  const Icon = tab.icon;
  return (
    <li className="flex-1">
      <Link
        href={tab.href}
        aria-current={active ? "page" : undefined}
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
        transition: "background 140ms ease-out",
      }}
    />
  );
}
