"use client";

/**
 * BottomNav — Dossier editorial bottom tab bar, mobile only.
 *
 * Rendered by <DashboardLayout/> below `md` (< 768px). Visual language
 * mirrors <TerminalSidebar/>: Vantablack ink ground, Ivory text, Bronze
 * accent on the active tab (top hairline + icon tint + label ink).
 *
 * Layout: 5 tabs fill the width. The fifth is "More" which opens a full
 * drawer (ModalShell, slides from bottom) with every remaining route —
 * Portfolio, Watchlist, Discover, Risk Board, Autotrade, Morning Brief,
 * Alerts, Reports, Settings — plus a Bronze-accent Sign Out at the foot.
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
  Bot,
  MessageSquare,
  BookHeart,
  Sun,
  FileText,
  Bell,
  Settings as SettingsIcon,
  LogOut,
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
};

// Primary bottom-bar tabs — chosen by CEO spec (Home / Market / Portfolio /
// Signals / More). Labels are literal (no locale dep) so a missing i18n key
// can never blank the bar on mobile.
const PRIMARY_TABS: Tab[] = [
  { href: "/home", label: "Home", icon: HomeIcon },
  { href: "/market", label: "Market", icon: Activity },
  { href: "/portfolio", label: "Portfolio", icon: Briefcase },
  { href: "/signals", label: "Signals", icon: Zap },
];

// Drawer contents — everything not in the bottom bar, grouped loosely by
// intent. Logout is rendered separately at the foot in a Bronze accent.
const DRAWER_ITEMS: Tab[] = [
  { href: "/watchlist", label: "Watchlist", icon: Eye },
  { href: "/discover", label: "Discover", icon: Compass },
  { href: "/risk", label: "Risk Board", icon: Shield },
  { href: "/autotrade", label: "Autotrade", icon: Bot },
  { href: "/ai-chat", label: "AI Chat", icon: MessageSquare },
  // Journal Companion — Closed Beta, Premium Plus / Founding Lifetime only.
  // Entitlement enforcement lives on /companion page; drawer just surfaces it.
  { href: "/companion", label: "Journal Companion", icon: BookHeart, premiumPlus: true },
  { href: "/morning-brief", label: "Morning Brief", icon: Sun },
  { href: "/reports", label: "Reports", icon: FileText },
  { href: "/alerts", label: "Alerts", icon: Bell },
  { href: "/settings", label: "Settings", icon: SettingsIcon },
];

function isRouteActive(pathname: string | null, href: string): boolean {
  if (!pathname) return false;
  return pathname === href || pathname.startsWith(href + "/");
}

export function BottomNav() {
  const pathname = usePathname();
  const router = useRouter();
  const { logout } = useAuth();
  const [drawerOpen, setDrawerOpen] = useState(false);

  // "More" is active whenever the current path matches any drawer route.
  const moreActive = DRAWER_ITEMS.some((it) => isRouteActive(pathname, it.href));

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
          borderTop: "0.5px solid rgba(245, 240, 232, 0.08)",
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
                  fontSize: "9.5px",
                  letterSpacing: "0.18em",
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
                borderBottom: "0.5px solid rgba(245, 240, 232, 0.08)",
              }}
            >
              <span
                className="font-serif uppercase"
                style={{
                  fontSize: "10.5px",
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
                className="flex h-9 w-9 items-center justify-center rounded-sm transition-colors hover:bg-[rgba(247,245,239,0.06)]"
              >
                <X
                  className="h-4 w-4"
                  strokeWidth={1.5}
                  style={{ color: "rgba(245, 240, 232, 0.6)" }}
                />
              </button>
            </div>

            {/* Drawer list */}
            <ul
              className="max-h-[65vh] overflow-y-auto px-2 py-2"
              role="list"
            >
              {DRAWER_ITEMS.map((item) => {
                const active = isRouteActive(pathname, item.href);
                const Icon = item.icon;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      onClick={() => setDrawerOpen(false)}
                      aria-current={active ? "page" : undefined}
                      className="flex items-center gap-3 rounded-sm font-serif uppercase transition-colors"
                      style={{
                        padding: "13px 14px",
                        fontSize: "12.5px",
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
                            fontSize: 8.5,
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

            {/* Sign out — Bronze-accent, hairline divider above */}
            <div
              className="px-2 pt-2"
              style={{
                borderTop: "0.5px solid rgba(245, 240, 232, 0.08)",
              }}
            >
              <button
                type="button"
                onClick={handleSignOut}
                className="flex w-full items-center gap-3 rounded-sm font-serif uppercase transition-colors hover:bg-[rgba(184,149,106,0.08)]"
                style={{
                  padding: "13px 14px",
                  fontSize: "12.5px",
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
            fontSize: "9.5px",
            letterSpacing: "0.18em",
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
