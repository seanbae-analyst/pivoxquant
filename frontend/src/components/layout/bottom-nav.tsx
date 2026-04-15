"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, BarChart3, Bot, Bell, Menu } from "lucide-react";
import { cn } from "@/lib/utils";

const TABS = [
  { href: "/home", label: "홈", icon: Home },
  { href: "/market", label: "시장", icon: BarChart3 },
  { href: "/ai", label: "AI", icon: Bot },
  { href: "/alerts", label: "알림", icon: Bell },
  { href: "/menu", label: "메뉴", icon: Menu },
] as const;

export function BottomNav() {
  const pathname = usePathname();

  return (
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
                "flex flex-1 flex-col items-center justify-center gap-1 py-1 transition-colors duration-200",
                isActive ? "text-purple-600" : "text-slate-400"
              )}
            >
              <Icon className="h-5 w-5" />
              <span className="text-[10px] font-medium">{tab.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
