"use client";

/**
 * TerminalSidebar — internal nav rail rendered inside every dashboard
 * terminal card (home, portfolio, watchlist, market, discover, risk).
 *
 * Visual language mirrors the original home-page sidebar: Vantablack
 * ink column, Bronze accent on active item, serif uppercase labels.
 */

import Link from "next/link";
import {
  Home as HomeIcon,
  Briefcase,
  Eye,
  Activity,
  Compass,
  Shield,
  Bell,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export type TerminalSidebarKey =
  | "home"
  | "portfolio"
  | "watchlist"
  | "market"
  | "discover"
  | "risk"
  | "alerts";

type Item = {
  key: TerminalSidebarKey;
  label: string;
  href: string;
  icon: LucideIcon;
};

const ITEMS: Item[] = [
  { key: "home", label: "Home", href: "/home", icon: HomeIcon },
  { key: "portfolio", label: "Portfolio", href: "/portfolio", icon: Briefcase },
  { key: "watchlist", label: "Watchlist", href: "/watchlist", icon: Eye },
  { key: "market", label: "Market", href: "/market", icon: Activity },
  { key: "discover", label: "Discover", href: "/discover", icon: Compass },
  { key: "risk", label: "Risk Board", href: "/risk", icon: Shield },
  { key: "alerts", label: "Alerts", href: "/alerts", icon: Bell },
];

export function TerminalSidebar({ active }: { active: TerminalSidebarKey }) {
  return (
    <aside
      className="hidden md:flex flex-col w-[220px] p-5 shrink-0 self-stretch"
      style={{ borderRight: "0.5pt solid rgba(245,240,232,0.08)" }}
    >
      <span
        className="font-serif text-[11px] uppercase mb-10"
        style={{
          letterSpacing: "0.22em",
          color: "var(--pq-ivory)",
          fontWeight: 500,
        }}
      >
        PIVOXQUANT
      </span>
      <nav className="space-y-0.5">
        {ITEMS.map((item) => {
          const isActive = active === item.key;
          const Icon = item.icon;
          return (
            <Link
              key={item.key}
              href={item.href}
              className="flex items-center gap-2.5 px-3 py-2.5 rounded-sm text-[12.5px] font-serif uppercase transition-colors"
              style={{
                letterSpacing: "0.2em",
                color: isActive
                  ? "var(--pq-ivory)"
                  : "rgba(245,240,232,0.5)",
                backgroundColor: isActive
                  ? "rgba(247,245,239,0.06)"
                  : "transparent",
                borderLeft: isActive
                  ? "2px solid var(--pq-bronze)"
                  : "2px solid transparent",
              }}
            >
              <Icon
                className="w-3.5 h-3.5 shrink-0"
                strokeWidth={1.5}
                style={{
                  color: isActive
                    ? "var(--pq-bronze)"
                    : "rgba(245,240,232,0.5)",
                }}
              />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
