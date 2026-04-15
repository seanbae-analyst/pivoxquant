"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Home,
  BarChart3,
  TrendingUp,
  Activity,
  Search,
  Eye,
  Bot,
  Zap,
  Shield,
  Settings,
  Crown,
  Sunrise,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/locale";

type NavKey =
  | "home"
  | "morningBrief"
  | "portfolio"
  | "market"
  | "signals"
  | "discover"
  | "watchlist"
  | "ai"
  | "autotrade"
  | "risk"
  | "settings";

const NAV_ITEMS: { href: string; key: NavKey; icon: React.ElementType }[] = [
  { href: "/home", key: "home", icon: Home },
  { href: "/morning-brief", key: "morningBrief", icon: Sunrise },
  { href: "/portfolio", key: "portfolio", icon: BarChart3 },
  { href: "/market", key: "market", icon: TrendingUp },
  { href: "/signals", key: "signals", icon: Activity },
  { href: "/discover", key: "discover", icon: Search },
  { href: "/watchlist", key: "watchlist", icon: Eye },
  { href: "/ai", key: "ai", icon: Bot },
  { href: "/autotrade", key: "autotrade", icon: Zap },
  { href: "/risk", key: "risk", icon: Shield },
  { href: "/settings", key: "settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const t = useT();

  return (
    <aside className="flex h-screen w-[220px] flex-col border-r border-slate-200 bg-white">
      {/* Logo */}
      <Link
        href="/home"
        aria-label="Go to home"
        className="flex h-16 items-center gap-2.5 px-5 transition-opacity hover:opacity-80"
      >
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-slate-900">
          <TrendingUp className="h-4 w-4 text-white" strokeWidth={1.75} />
        </div>
        <span className="text-base font-semibold text-slate-900 tracking-tight">PivoxQuant</span>
      </Link>

      {/* Navigation */}
      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-2 scrollbar-thin">
        {NAV_ITEMS.map((item) => {
          const isActive =
            pathname === item.href || pathname?.startsWith(item.href + "/");
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors duration-150",
                isActive
                  ? "bg-slate-100 text-slate-900"
                  : "text-slate-500 hover:bg-slate-50 hover:text-slate-900",
              )}
            >
              <Icon
                className={cn(
                  "h-[18px] w-[18px] shrink-0",
                  isActive ? "text-slate-900" : "text-slate-400",
                )}
                strokeWidth={1.75}
              />
              <span>{t(`nav.${item.key}`)}</span>
            </Link>
          );
        })}
      </nav>

      {/* Upgrade CTA */}
      <div className="p-3">
        <Link
          href="/pricing"
          className="flex items-center justify-center gap-2 rounded-md bg-slate-900 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-slate-800"
        >
          <Crown className="h-4 w-4" strokeWidth={1.75} />
          <span>{t("nav.upgrade")}</span>
        </Link>
      </div>
    </aside>
  );
}
