"use client";

/**
 * TerminalSidebar — full-height Vantablack navigation rail.
 *
 * Rendered by <DashboardLayout/> at the left edge of every desktop
 * dashboard view. Visual language mirrors the landing Dashboard
 * Preview: ink column, bronze left-edge accent on the active item,
 * editorial uppercase labels with generous spacing.
 *
 * Props:
 *   - variant: "rail" (default) — fills its parent column (240px in
 *     DashboardLayout). Self-determines the active item from the URL
 *     via `usePathname`.
 *   - active: legacy opt-in override for callers that still want to
 *     force a particular key (tests, embedded previews). Ignored by
 *     default.
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
  Bot,
  Sun,
  FileText,
  Bell,
  Settings as SettingsIcon,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export type TerminalSidebarKey =
  | "home"
  | "portfolio"
  | "watchlist"
  | "market"
  | "discover"
  | "risk"
  | "signals"
  | "ai-chat"
  | "autotrade"
  | "morning-brief"
  | "reports"
  | "alerts"
  | "settings";

type Item = {
  key: TerminalSidebarKey;
  label: string;
  href: string;
  icon: LucideIcon;
};

const PRIMARY_ITEMS: Item[] = [
  { key: "home", label: "Home", href: "/home", icon: HomeIcon },
  { key: "portfolio", label: "Portfolio", href: "/portfolio", icon: Briefcase },
  { key: "watchlist", label: "Watchlist", href: "/watchlist", icon: Eye },
  { key: "market", label: "Market", href: "/market", icon: Activity },
  { key: "discover", label: "Discover", href: "/discover", icon: Compass },
  { key: "risk", label: "Risk Board", href: "/risk", icon: Shield },
  { key: "signals", label: "Signals", href: "/signals", icon: Zap },
  { key: "ai-chat", label: "AI Chat", href: "/ai-chat", icon: MessageSquare },
  { key: "autotrade", label: "Autotrade", href: "/autotrade", icon: Bot },
];

const SECONDARY_ITEMS: Item[] = [
  { key: "morning-brief", label: "Morning Brief", href: "/morning-brief", icon: Sun },
  { key: "reports", label: "Reports", href: "/reports", icon: FileText },
  { key: "alerts", label: "Alerts", href: "/alerts", icon: Bell },
  { key: "settings", label: "Settings", href: "/settings", icon: SettingsIcon },
];

function keyFromPath(pathname: string | null): TerminalSidebarKey | null {
  if (!pathname) return null;
  const all = [...PRIMARY_ITEMS, ...SECONDARY_ITEMS];
  // Longest-prefix match so "/portfolio/123" lights Portfolio.
  const match = all
    .slice()
    .sort((a, b) => b.href.length - a.href.length)
    .find((it) => pathname === it.href || pathname.startsWith(it.href + "/"));
  return match?.key ?? null;
}

export function TerminalSidebar({
  active,
  variant: _variant = "rail",
}: {
  active?: TerminalSidebarKey;
  variant?: "rail";
}) {
  const pathname = usePathname();
  const resolvedActive = active ?? keyFromPath(pathname);

  return (
    <div className="flex h-full flex-col">
      {/* Brand mark */}
      <div className="px-6 pt-7 pb-6">
        <span
          className="font-serif uppercase"
          style={{
            fontSize: "11px",
            letterSpacing: "0.22em",
            color: "var(--pq-ivory)",
            fontWeight: 500,
          }}
        >
          PIVOXQUANT
        </span>
      </div>

      {/* Primary nav */}
      <nav className="px-3" aria-label="Primary">
        <ul className="space-y-0.5">
          {PRIMARY_ITEMS.map((item) => (
            <SidebarLink
              key={item.key}
              item={item}
              isActive={resolvedActive === item.key}
            />
          ))}
        </ul>
      </nav>

      {/* Hairline separator */}
      <div
        aria-hidden="true"
        style={{
          borderTop: "0.5px solid rgba(245,240,232,0.08)",
          margin: "16px 12px",
        }}
      />

      {/* Secondary nav */}
      <nav className="flex-1 px-3" aria-label="Secondary">
        <ul className="space-y-0.5">
          {SECONDARY_ITEMS.map((item) => (
            <SidebarLink
              key={item.key}
              item={item}
              isActive={resolvedActive === item.key}
            />
          ))}
        </ul>
      </nav>

      {/* Footer meta */}
      <div className="px-6 pb-6 pt-4">
        <span
          className="block font-mono uppercase"
          style={{
            fontSize: "9px",
            letterSpacing: "0.22em",
            color: "rgba(245,240,232,0.35)",
          }}
        >
          v1.0 · Paper
        </span>
      </div>
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
          fontSize: "12.5px",
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
