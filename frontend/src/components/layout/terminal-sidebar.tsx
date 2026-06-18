"use client";

/**
 * TerminalSidebar — full-height Vantablack navigation rail.
 *
 * 2026-06-15 (CEO 19→3): collapsed to a 3-door IA — Mirror /
 * Portfolio / Pre-Trade up top, everything else under "More";
 * growth/market/discover/watchlist/ai-chat hidden (pages preserved).
 * The 4-group notes below are legacy.
 *
 * IA (2026-06-10 record-as-spine reorg, CEO GO on
 * docs/strategy/record-as-spine_2026-06-09.md §4.1): Home (top, ungrouped)
 * + 4 thematic groups —
 *   RECORD     · 기록 — 척추 본체 (Journal / Pre-Trade / Routine)
 *   ARTIFACTS  · 기록의 요약본 (Reports)
 *   OBSERVE    · 관측 — 기록에 먹이를 주는 입력단 (Portfolio / Signals /
 *                Risk / AI Analysis; Market·Discover·AI Chat·Watchlist hidden)
 *   SYSTEM     · 도구·계정 (Alerts / Companion / Profile · Persona / Settings)
 *
 * Previous IA buried Journal·Pre-Trade·Routine at the bottom of "System"
 * next to Settings while the brand sells "거래 전 거울 / compounding
 * memory" — the spine sat in the appendix slot. The reorg promotes the
 * record to the first group. Portfolio leads OBSERVE (highest-traffic
 * destination; the memo's sketch listed it last but did not intend a
 * demotion).
 *
 * Note: /growth (Growth OS — a habit/reflection routine tracker) is
 * surfaced as "Routine". The label avoids the word "Growth" to prevent
 * confusion with capital-market asset-growth/return language under KR
 * financial advisory law (§101).
 *
 * Profile · Persona surfaces the account + investor-persona page directly
 * in the rail (it was previously only reachable via the top-bar avatar).
 * Detail/[ticker] is dynamic and not surfaced.
 *
 * Visual language: ink column, bronze left-edge accent on the active
 * item, editorial uppercase labels with generous spacing. Group labels
 * use the bronze tint at 55% with a hairline divider directly under.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { isDemoMode } from "@/lib/demo";
import {
  Home as HomeIcon,
  Briefcase,
  Eye,
  Activity,
  Compass,
  Shield,
  Zap,
  MessageSquare,
  FileText,
  Bell,
  Settings as SettingsIcon,
  Sparkles,
  BookHeart,
  NotebookPen,
  UserCircle,
  Sprout,
  Gavel,
  Contrast,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export type TerminalSidebarKey =
  | "home"
  | "mirror"
  // "morning-brief" key REMOVED 2026-04-29 — backend deprecated.
  | "reports"
  | "signals"
  | "portfolio"
  | "watchlist"
  | "risk"
  // REMOVED 2026-04-27 per CEO + legal: "autotrade" key retired.
  | "market"
  | "discover"
  | "ai-chat"
  | "ai"
  | "alerts"
  | "companion"
  | "pre-trade"
  | "journal"
  | "growth"
  | "profile"
  | "settings";

type Item = {
  key: TerminalSidebarKey;
  label: string;
  href: string;
  icon: LucideIcon;
  /**
   * If true, the item is excluded from rendering but kept in the array
   * so that routes/keys/active-state resolution remains intact and any
   * deep links (e.g. /watchlist) still light the correct active key
   * when the user navigates there directly. 2026-04-27 per CEO: hide
   * Morning Brief / Watchlist / Market / Discover / AI Chat from the
   * rail while preserving the underlying pages.
   */
  hidden?: boolean;
};

// PRIMARY — the 3 doors. 19→3 reduction (CEO 2026-06-15): the behavioural
// loop IS the product (멈춤 → 기록 → 거울). Everything else is demoted to
// "More" or hidden — NO pages deleted, all still reachable.
const PRIMARY: Item[] = [
  { key: "mirror", label: "Mirror", href: "/mirror", icon: Contrast },
  { key: "portfolio", label: "Portfolio", href: "/portfolio", icon: Briefcase },
  { key: "pre-trade", label: "Pre-Trade", href: "/pre-trade", icon: Gavel },
];

// MORE — demoted but fully reachable (no longer competing for attention).
const MORE: Item[] = [
  { key: "home", label: "Home", href: "/home", icon: HomeIcon },
  { key: "journal", label: "Journal", href: "/journal", icon: NotebookPen },
  { key: "reports", label: "Reports", href: "/reports", icon: FileText },
  { key: "risk", label: "Risk Board", href: "/risk", icon: Shield },
  { key: "signals", label: "Signals", href: "/signals", icon: Zap },
  { key: "ai", label: "AI Analysis", href: "/ai", icon: Sparkles },
  { key: "alerts", label: "Alerts", href: "/alerts", icon: Bell },
  { key: "companion", label: "Companion", href: "/companion", icon: BookHeart },
  { key: "profile", label: "Profile · Persona", href: "/profile", icon: UserCircle },
  { key: "settings", label: "Settings", href: "/settings", icon: SettingsIcon },
];

// HIDDEN — pages preserved, off-nav (deep-link + active-state still resolve).
// Closed doors: growth = founder's personal "Solo Founder Growth OS" (not a
// user feature); market / discover = generic data available anywhere;
// watchlist / ai-chat = superseded surfaces.
const HIDDEN: Item[] = [
  { key: "growth", label: "Routine", href: "/growth", icon: Sprout, hidden: true },
  { key: "watchlist", label: "Watchlist", href: "/watchlist", icon: Eye, hidden: true },
  { key: "market", label: "Market", href: "/market", icon: Activity, hidden: true },
  { key: "discover", label: "Discover", href: "/discover", icon: Compass, hidden: true },
  { key: "ai-chat", label: "AI Chat", href: "/ai-chat", icon: MessageSquare, hidden: true },
];

const ALL_ITEMS: Item[] = [...PRIMARY, ...MORE, ...HIDDEN];

// DEMO mode: AI surfaces depend on paid Anthropic tokens to function, so they
// are dropped from the nav in the portfolio demo (pages preserved; CEO 2026-06-18).
const DEMO_HIDDEN_KEYS = new Set(["ai", "companion"]);
const isDemoHidden = (key: string) => isDemoMode() && DEMO_HIDDEN_KEYS.has(key);

function keyFromPath(pathname: string | null): TerminalSidebarKey | null {
  if (!pathname) return null;
  // Longest-prefix match so "/portfolio/123" lights Portfolio.
  const match = ALL_ITEMS.slice()
    .sort((a, b) => b.href.length - a.href.length)
    .find((it) => pathname === it.href || pathname.startsWith(it.href + "/"));
  return match?.key ?? null;
}

export function TerminalSidebar({
  active,
}: {
  active?: TerminalSidebarKey;
  /** Reserved for future layouts; currently fixed to "rail". */
  variant?: "rail";
}) {
  const pathname = usePathname();
  const resolvedActive = active ?? keyFromPath(pathname);

  return (
    <div className="flex h-full flex-col">
      {/* Brand mark — FINDING-030: canonical wordmark is italic Playfair
          Display mixed-case "PivoxQuant" (splash + landing + market all use
          this form). The sidebar previously rendered roman uppercase
          "PIVOXQUANT", a competing second treatment. Now unified. */}
      <div className="px-6 pt-7 pb-6">
        <span
          className="font-serif"
          style={{
            fontSize: "var(--pq-text-h6)",
            letterSpacing: "0.01em",
            color: "var(--pq-ivory)",
            fontWeight: 500,
          }}
        >
          PivoxQuant
        </span>
      </div>

      {/* Scrollable nav body */}
      <nav className="flex-1 overflow-y-auto" aria-label="Primary">
        {/* The 3 doors — Mirror / Portfolio / Pre-Trade */}
        <ul className="space-y-0.5 px-3" aria-label="Primary doors">
          {PRIMARY.filter((it) => !it.hidden).map((item) => (
            <SidebarLink
              key={item.key}
              item={item}
              isActive={resolvedActive === item.key}
            />
          ))}
        </ul>

        <GroupHeader label="More" />
        <ul className="space-y-0.5 px-3 pb-4" aria-label="More">
          {MORE.filter((it) => !it.hidden && !isDemoHidden(it.key)).map((item) => (
            <SidebarLink
              key={item.key}
              item={item}
              isActive={resolvedActive === item.key}
            />
          ))}
        </ul>
      </nav>

      {/* Footer meta — FINDING-040: "v1.0 · Paper" was ambiguous ("paper"
          as document? paper trade?). Spell out the mode so the observation-
          only posture is unmistakable. */}
      <div className="px-6 pb-6 pt-4">
        <span
          className="block font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-kicker)",
            letterSpacing: "0.22em",
            color: "rgba(245,240,232,0.55)",
          }}
          title="Paper mode — broker orders disabled, observation only"
        >
          v1.0 · Paper mode (observation only)
        </span>
      </div>
    </div>
  );
}

function GroupHeader({ label }: { label: string }) {
  return (
    <div className="px-3 mt-6 mb-2" aria-hidden="true">
      <span
        className="font-serif uppercase"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.22em",
          color: "rgba(184, 149, 106, 0.55)",
          display: "block",
          paddingLeft: "14px",
        }}
      >
        {label}
      </span>
      <div
        className="mt-1 h-px"
        style={{ backgroundColor: "var(--pq-ivory-line)" }}
      />
    </div>
  );
}

function SidebarLink({ item, isActive }: { item: Item; isActive: boolean }) {
  const Icon = item.icon;
  return (
    <li>
      <Link
        href={item.href}
        aria-current={isActive ? "page" : undefined}
        className="flex items-center gap-2.5 rounded-sm font-serif uppercase transition-colors"
        style={{
          padding: "10px 14px",
          fontSize: "var(--pq-text-body)",
          letterSpacing: "0.2em",
          color: isActive ? "var(--pq-ivory)" : "rgba(245,240,232,0.5)",
          backgroundColor: isActive ? "rgba(247,245,239,0.06)" : "transparent",
          borderLeft: isActive
            ? "3px solid var(--pq-bronze)"
            : "3px solid transparent",
        }}
      >
        <Icon
          className="h-3.5 w-3.5 shrink-0"
          strokeWidth={1.5}
          style={{
            color: isActive ? "var(--pq-bronze)" : "rgba(245,240,232,0.5)",
          }}
        />
        {item.label}
      </Link>
    </li>
  );
}
