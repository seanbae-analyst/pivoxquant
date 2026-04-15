"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Home,
  BarChart3,
  Bot,
  Bell,
  Menu,
  TrendingUp,
  Activity,
  Search,
  Eye,
  Zap,
  Shield,
  Settings,
  Sunrise,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { ModalShell } from "@/components/ui/modal-shell";
import { useT } from "@/lib/locale";

const TABS = [
  { href: "/home", label: "홈", icon: Home },
  { href: "/market", label: "시장", icon: BarChart3 },
  { href: "/ai", label: "AI", icon: Bot },
  { href: "/alerts", label: "알림", icon: Bell },
] as const;

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

const MENU_ITEMS: { href: string; key: NavKey; icon: React.ElementType }[] = [
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

export function BottomNav() {
  const pathname = usePathname();
  const t = useT();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <>
      <nav className="fixed inset-x-0 bottom-0 z-50 border-t border-slate-200 bg-white/90 backdrop-blur-lg safe-area-pb md:hidden">
        <div className="flex h-16 items-center justify-around px-2">
          {TABS.map((tab) => {
            const isActive =
              pathname === tab.href || pathname?.startsWith(tab.href + "/");
            const Icon = tab.icon;

            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={cn(
                  "flex flex-1 flex-col items-center justify-center gap-1 py-1 transition-colors duration-150",
                  isActive ? "text-slate-900" : "text-slate-400 hover:text-slate-700"
                )}
              >
                <Icon className="h-5 w-5" strokeWidth={1.75} />
                <span className="text-[10px] font-medium">{tab.label}</span>
              </Link>
            );
          })}

          {/* Menu tab — opens the full nav sheet */}
          <button
            type="button"
            onClick={() => setMenuOpen(true)}
            aria-label="메뉴 열기"
            aria-expanded={menuOpen}
            className={cn(
              "flex flex-1 flex-col items-center justify-center gap-1 py-1 transition-colors duration-150",
              menuOpen ? "text-slate-900" : "text-slate-400 hover:text-slate-700"
            )}
          >
            <Menu className="h-5 w-5" strokeWidth={1.75} />
            <span className="text-[10px] font-medium">메뉴</span>
          </button>
        </div>
      </nav>

      {menuOpen && (
        <ModalShell
          onClose={() => setMenuOpen(false)}
          ariaLabel="메뉴"
          className="!items-end sm:!items-end"
        >
          <div className="w-full max-w-md rounded-t-2xl border border-slate-200 bg-white shadow-2xl sm:rounded-2xl">
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
              <h3 className="text-sm font-semibold text-slate-900">메뉴</h3>
              <button
                type="button"
                onClick={() => setMenuOpen(false)}
                aria-label="닫기"
                className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <nav className="grid max-h-[70vh] grid-cols-2 gap-1 overflow-y-auto p-2">
              {MENU_ITEMS.map((item) => {
                const isActive =
                  pathname === item.href ||
                  pathname?.startsWith(item.href + "/");
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMenuOpen(false)}
                    className={cn(
                      "flex items-center gap-3 rounded-md px-3 py-3 text-sm font-medium transition-colors",
                      isActive
                        ? "bg-slate-100 text-slate-900"
                        : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                    )}
                  >
                    <Icon
                      className={cn(
                        "h-[18px] w-[18px] shrink-0",
                        isActive ? "text-slate-900" : "text-slate-400"
                      )}
                      strokeWidth={1.75}
                    />
                    <span className="truncate">{t(`nav.${item.key}`)}</span>
                  </Link>
                );
              })}
            </nav>
          </div>
        </ModalShell>
      )}
    </>
  );
}
