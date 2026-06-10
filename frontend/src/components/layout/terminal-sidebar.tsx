"use client";

/**
 * TerminalSidebar — full-height Vantablack navigation rail.
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

// Top — ungrouped, sits above the first group label.
const TOP: Item[] = [
  { key: "home", label: "Home", href: "/home", icon: HomeIcon },
];

// ── RECORD — 기록 (척추 본체) ──────────────────────────────────────
// 2026-06-10 record-as-spine reorg: Journal / Pre-Trade / Routine were
// previously buried at the bottom of "System" next to Settings. They are
// the product's most differentiated surfaces — promoted to the first group.
const RECORD: Item[] = [
  // /journal renders the user's own pre-trade decision-reflection feed +
  // 5 Behavior Mirrors (read-only, "User as CFO"). Restored 2026-05-21.
  { key: "journal", label: "Journal", href: "/journal", icon: NotebookPen },
  // 2026-06-10: "Pre-Trade" RESTORED (was removed 2026-05-21 as
  // "redundant with the inline modal"). The record-as-spine memo (§4.1,
  // CEO GO) re-establishes it as the deposition's direct entry point —
  // the inline modal stays the primary path; this is the standalone door.
  { key: "pre-trade", label: "Pre-Trade", href: "/pre-trade", icon: Gavel },
  // 2026-05-28: Growth OS (/growth) surfaced in the rail per CEO. Earlier
  // comment claimed "agent_worker backend not deployed → 준비 중" — STALE:
  // verified live in prod (/api/growth/{today,data,weekly}=401-behind-auth,
  // /reflect=405). It is a habit/reflection routine tracker; label "Routine"
  // avoids the asset-growth/return implication of "Growth" under §101.
  { key: "growth", label: "Routine", href: "/growth", icon: Sprout },
];

// ── ARTIFACTS — 기록의 요약본 (CFO 생산물) ─────────────────────────
// REMOVED 2026-04-29: Morning Brief item retired (backend deprecated).
// 2026-06-10: Signals moved to OBSERVE (it is an input that feeds the
// record, not a produced report).
const ARTIFACTS: Item[] = [
  { key: "reports", label: "Reports", href: "/reports", icon: FileText },
];

// ── OBSERVE — 관측 (기록에 먹이를 주는 입력단) ─────────────────────
// 2026-06-10: renamed from RESEARCH and absorbs the old PORTFOLIO group —
// portfolio positions, signals and the risk board are all observation
// inputs in the record loop (관측 → 성찰·기록 → 리뷰 → 복리).
const OBSERVE: Item[] = [
  { key: "portfolio", label: "Portfolio", href: "/portfolio", icon: Briefcase },
  { key: "signals", label: "Signals", href: "/signals", icon: Zap },
  { key: "risk", label: "Risk Board", href: "/risk", icon: Shield },
  // REMOVED 2026-04-27 per CEO + legal: autotrade item (투자일임업 회피).
  { key: "ai", label: "AI Analysis", href: "/ai", icon: Sparkles },
  {
    key: "watchlist",
    label: "Watchlist",
    href: "/watchlist",
    icon: Eye,
    hidden: true,
  },
  {
    key: "market",
    label: "Market",
    href: "/market",
    icon: Activity,
    hidden: true,
  },
  {
    key: "discover",
    label: "Discover",
    href: "/discover",
    icon: Compass,
    hidden: true,
  },
  {
    key: "ai-chat",
    label: "AI Chat",
    href: "/ai-chat",
    icon: MessageSquare,
    hidden: true,
  },
];

// ── SYSTEM — 알림·도구·설정 ────────────────────────────────────────
const SYSTEM: Item[] = [
  { key: "alerts", label: "Alerts", href: "/alerts", icon: Bell },
  { key: "companion", label: "Companion", href: "/companion", icon: BookHeart },
  {
    key: "profile",
    label: "Profile · Persona",
    href: "/profile",
    icon: UserCircle,
  },
  { key: "settings", label: "Settings", href: "/settings", icon: SettingsIcon },
  // Methodology moved to a PUBLIC landing page (/methodology) 2026-06-05 per CEO
  // — no longer a login-gated sidebar item.
];

const ALL_ITEMS: Item[] = [
  ...TOP,
  ...RECORD,
  ...ARTIFACTS,
  ...OBSERVE,
  ...SYSTEM,
];

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

        {/* aria-label on each <ul> — the visual GroupHeader is aria-hidden,
            which left screen readers one flat 13-link list (design audit
            2026-06-10). Labelled lists restore the record-as-spine grouping
            for AT users. */}
        <GroupHeader label="Record" />
        <ul className="space-y-0.5 px-3" aria-label="Record">
          {RECORD.filter((it) => !it.hidden).map((item) => (
            <SidebarLink
              key={item.key}
              item={item}
              isActive={resolvedActive === item.key}
            />
          ))}
        </ul>

        <GroupHeader label="Artifacts" />
        <ul className="space-y-0.5 px-3" aria-label="Artifacts">
          {ARTIFACTS.filter((it) => !it.hidden).map((item) => (
            <SidebarLink
              key={item.key}
              item={item}
              isActive={resolvedActive === item.key}
            />
          ))}
        </ul>

        <GroupHeader label="Observe" />
        <ul className="space-y-0.5 px-3" aria-label="Observe">
          {OBSERVE.filter((it) => !it.hidden).map((item) => (
            <SidebarLink
              key={item.key}
              item={item}
              isActive={resolvedActive === item.key}
            />
          ))}
        </ul>

        <GroupHeader label="System" />
        <ul className="space-y-0.5 px-3 pb-4" aria-label="System">
          {SYSTEM.filter((it) => !it.hidden).map((item) => (
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
