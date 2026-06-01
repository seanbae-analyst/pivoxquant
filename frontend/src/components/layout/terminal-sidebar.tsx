"use client";

/**
 * TerminalSidebar — full-height Vantablack navigation rail.
 *
 * IA: Home (top, ungrouped) + 4 thematic groups —
 *   ARTIFACTS  · CFO 생산물 (Morning Brief / Reports / Signals)
 *   PORTFOLIO  · 자산 관리 (Portfolio / Watchlist / Risk / Autotrade)
 *   RESEARCH   · 조사·분석 (Market / Discover / AI Chat / AI Analysis)
 *   SYSTEM     · 도구·계정 (Alerts / Companion / Journal / Profile · Persona / Settings)
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
  Sigma,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export type TerminalSidebarKey =
  | "home"
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
  | "settings"
  | "methodology";

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

// Top — ungrouped, sits above the first group label.
const TOP: Item[] = [
  { key: "home", label: "Home", href: "/home", icon: HomeIcon },
];

// ── ARTIFACTS — CFO 생산물 ──────────────────────────────────────────
// REMOVED 2026-04-29: Morning Brief item retired (backend deprecated).
const ARTIFACTS: Item[] = [
  { key: "reports", label: "Reports", href: "/reports", icon: FileText },
  { key: "signals", label: "Signals", href: "/signals", icon: Zap },
];

// ── PORTFOLIO — 자산 관리 ──────────────────────────────────────────
const PORTFOLIO: Item[] = [
  { key: "portfolio", label: "Portfolio", href: "/portfolio", icon: Briefcase },
  { key: "watchlist", label: "Watchlist", href: "/watchlist", icon: Eye, hidden: true },
  { key: "risk", label: "Risk Board", href: "/risk", icon: Shield },
  // REMOVED 2026-04-27 per CEO + legal: autotrade item (투자일임업 회피).
];

// ── RESEARCH — 조사·분석 ───────────────────────────────────────────
const RESEARCH: Item[] = [
  { key: "market", label: "Market", href: "/market", icon: Activity, hidden: true },
  { key: "discover", label: "Discover", href: "/discover", icon: Compass, hidden: true },
  { key: "ai-chat", label: "AI Chat", href: "/ai-chat", icon: MessageSquare, hidden: true },
  { key: "ai", label: "AI Analysis", href: "/ai", icon: Sparkles },
];

// ── SYSTEM — 알림·도구·설정 ────────────────────────────────────────
const SYSTEM: Item[] = [
  { key: "alerts", label: "Alerts", href: "/alerts", icon: Bell },
  // 2026-05-21: "Pre-Trade" nav item REMOVED entirely (per CEO). The
  // 7-question + cooldown reflection is now INLINE at position add (ENTRY) /
  // exit (EXIT), so a standalone nav destination is redundant. The /pre-trade
  // route still resolves for direct/deep links; the past reflections are
  // reviewed in Journal (/journal).
  { key: "companion", label: "Companion", href: "/companion", icon: BookHeart },
  // 2026-05-21: "Journal" restored as a real user surface — /journal renders
  // the user's own pre-trade decision-reflection feed (read-only, "User as
  // CFO").
  { key: "journal", label: "Journal", href: "/journal", icon: NotebookPen },
  // 2026-05-28: Growth OS (/growth) surfaced in the rail per CEO. Earlier
  // comment claimed "agent_worker backend not deployed → 준비 중" — STALE:
  // verified live in prod (/api/growth/{today,data,weekly}=401-behind-auth,
  // /reflect=405). It is a habit/reflection routine tracker; label "Routine"
  // avoids the asset-growth/return implication of "Growth" under §101.
  { key: "growth", label: "Routine", href: "/growth", icon: Sprout },
  { key: "profile", label: "Profile · Persona", href: "/profile", icon: UserCircle },
  { key: "settings", label: "Settings", href: "/settings", icon: SettingsIcon },
  // 2026-06-01: Methodology trust surface (/methodology). Login-gated until
  // Q-DT4 (METHODOLOGY_PUBLIC flag); surfaced here so beta users can read how
  // the engine works (40-model catalog + academic sources + data lineage).
  { key: "methodology", label: "Methodology", href: "/methodology", icon: Sigma },
];

const ALL_ITEMS: Item[] = [...TOP, ...ARTIFACTS, ...PORTFOLIO, ...RESEARCH, ...SYSTEM];

function keyFromPath(pathname: string | null): TerminalSidebarKey | null {
  if (!pathname) return null;
  // Longest-prefix match so "/portfolio/123" lights Portfolio.
  const match = ALL_ITEMS
    .slice()
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
          className="font-serif italic"
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
        {/* TOP — Home (ungrouped) */}
        <ul className="space-y-0.5 px-3">
          {TOP.filter((it) => !it.hidden).map((item) => (
            <SidebarLink
              key={item.key}
              item={item}
              isActive={resolvedActive === item.key}
            />
          ))}
        </ul>

        <GroupHeader label="Artifacts" />
        <ul className="space-y-0.5 px-3">
          {ARTIFACTS.filter((it) => !it.hidden).map((item) => (
            <SidebarLink key={item.key} item={item} isActive={resolvedActive === item.key} />
          ))}
        </ul>

        <GroupHeader label="Portfolio" />
        <ul className="space-y-0.5 px-3">
          {PORTFOLIO.filter((it) => !it.hidden).map((item) => (
            <SidebarLink key={item.key} item={item} isActive={resolvedActive === item.key} />
          ))}
        </ul>

        <GroupHeader label="Research" />
        <ul className="space-y-0.5 px-3">
          {RESEARCH.filter((it) => !it.hidden).map((item) => (
            <SidebarLink key={item.key} item={item} isActive={resolvedActive === item.key} />
          ))}
        </ul>

        <GroupHeader label="System" />
        <ul className="space-y-0.5 px-3 pb-4">
          {SYSTEM.filter((it) => !it.hidden).map((item) => (
            <SidebarLink key={item.key} item={item} isActive={resolvedActive === item.key} />
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
          backgroundColor: isActive
            ? "rgba(247,245,239,0.06)"
            : "transparent",
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
