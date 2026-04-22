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
  Bell,
  FileText,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/locale";
import { useArtifacts } from "@/lib/hooks";
import { useAuth } from "@/lib/auth";

/* ──────────────────────────────────────────────────────────────
   Sidebar — Vantablack rail, Bronze active accent.
   Palette + motion lifted from the landing page's Research
   Terminal preview (landing-page.tsx §6, lines 3088–3128) so
   users hitting /home land in the exact surface they saw on
   the marketing site. All Nexora purple/pink gradient legacy
   tokens removed.
   ────────────────────────────────────────────────────────────── */

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
  | "alerts"
  | "reports"
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
  { href: "/alerts", key: "alerts", icon: Bell },
  { href: "/reports", key: "reports", icon: FileText },
  { href: "/settings", key: "settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const t = useT();
  // Unread artifact badge — tiny bronze dot next to Reports when >0 unread.
  const { unreadCount } = useArtifacts();
  const { user } = useAuth();
  // Hide upgrade CTA for paid users.
  const isPaid =
    user?.subscription_tier === "premium" || user?.subscription_tier === "pro";

  return (
    <aside
      className="flex h-screen w-[220px] flex-col"
      style={{
        backgroundColor: "var(--pq-ink)",
        borderRight: "1px solid var(--pq-hairline-ink, rgba(245,240,232,0.08))",
      }}
    >
      {/* Wordmark — matches landing top-left PIVOX QUANT mark */}
      <Link
        href="/home"
        aria-label="Go to PivoxQuant home"
        className="flex h-16 items-center px-5 transition-opacity hover:opacity-80"
      >
        <span className="pq-side-wordmark">PIVOX&nbsp;QUANT</span>
      </Link>

      {/* Navigation rail */}
      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-2 scrollbar-thin">
        {NAV_ITEMS.map((item) => {
          const isActive =
            pathname === item.href || pathname?.startsWith(item.href + "/");
          const Icon = item.icon;
          const showUnreadDot = item.key === "reports" && unreadCount > 0;

          return (
            <Link
              key={item.href}
              href={item.href}
              data-active={isActive}
              className={cn("pq-side-link rounded-[2px]")}
            >
              <Icon
                className="h-[16px] w-[16px] shrink-0"
                strokeWidth={1.5}
                aria-hidden
              />
              <span className="flex-1 truncate">{t(`nav.${item.key}`)}</span>
              {showUnreadDot && (
                <span
                  aria-label={`${unreadCount} unread`}
                  className="inline-flex h-1.5 w-1.5 shrink-0 rounded-full"
                  style={{ backgroundColor: "var(--pq-bronze)" }}
                />
              )}
            </Link>
          );
        })}
      </nav>

      {/* Upgrade CTA — bronze fill on ink (matches landing primary CTA) */}
      {!isPaid && (
        <div className="p-4">
          <Link
            href="/pricing"
            className="flex items-center justify-center gap-2 rounded-[2px] px-4 py-2.5 font-serif text-[12px] tracking-[0.05em] transition-colors"
            style={{
              backgroundColor: "var(--pq-bronze)",
              color: "var(--pq-ink)",
            }}
            onMouseEnter={(e) =>
              (e.currentTarget.style.backgroundColor = "var(--pq-bronze-light)")
            }
            onMouseLeave={(e) =>
              (e.currentTarget.style.backgroundColor = "var(--pq-bronze)")
            }
          >
            <Crown className="h-3.5 w-3.5" strokeWidth={1.5} />
            <span className="uppercase">{t("nav.upgrade")}</span>
          </Link>
        </div>
      )}
    </aside>
  );
}
