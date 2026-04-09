"use client";

import { useAuth } from "@/lib/auth";
import { useRouter, usePathname } from "next/navigation";
import { useEffect } from "react";
import Link from "next/link";
import { Logo } from "@/components/ui/logo";
import { MarketTicker } from "@/components/layout/market-ticker";
import { InstallPrompt } from "@/components/pwa/install-prompt";

/* Navigation structure */

const directLinks = [
  { label: "Portfolio", href: "/" },
  { label: "Market", href: "/market" },
  { label: "Trading", href: "/autotrade" },
];

const dropdowns: { label: string; items: { label: string; href: string }[] }[] = [
  {
    label: "AI",
    items: [
      { label: "Chat", href: "/ai-chat" },
      { label: "Trade Ideas", href: "/ai-ideas" },
      { label: "Smart Alerts", href: "/ai-alerts" },
      { label: "Portfolio Review", href: "/ai-review" },
    ],
  },
  {
    label: "Analysis",
    items: [
      { label: "Monte Carlo", href: "/monte-carlo" },
      { label: "Benchmark", href: "/benchmark" },
      { label: "Attribution", href: "/attribution" },
      { label: "Factors", href: "/factors" },
      { label: "Correlation", href: "/correlation" },
      { label: "Stress Test", href: "/stress-test" },
      { label: "Risk", href: "/risk" },
    ],
  },
  {
    label: "Tools",
    items: [
      { label: "Optimizer", href: "/optimizer" },
      { label: "Sector Rotation", href: "/sector-rotation" },
      { label: "Kelly Sizing", href: "/kelly" },
      { label: "Backtest", href: "/backtest" },
      { label: "Dividends", href: "/dividends" },
      { label: "Tax", href: "/tax" },
      { label: "Earnings", href: "/earnings" },
      { label: "News", href: "/news" },
      { label: "Peers", href: "/peers" },
      { label: "Copy Trading", href: "/copy-trading" },
    ],
  },
];

const rightLinks = [
  { label: "Alerts", href: "/alerts" },
  { label: "Trades", href: "/trades" },
  { label: "Watchlist", href: "/watchlist" },
];

/* Dropdown component */

function NavDropdown({ label, items, pathname }: { label: string; items: { label: string; href: string }[]; pathname: string }) {
  const isActive = items.some(i => pathname.startsWith(i.href) && i.href !== "/");

  return (
    <div className="group/dd relative">
      <button
        className={`text-[12px] font-medium px-3 py-1.5 rounded-lg spring-transition transition-all duration-300 whitespace-nowrap flex items-center gap-1 ${
          isActive
            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/15"
            : "text-zinc-500 hover:text-zinc-200 hover:bg-[rgba(255,255,255,0.04)]"
        }`}
      >
        {label}
        <svg width="8" height="8" viewBox="0 0 10 10" className="spring-transition transition-transform duration-300 group-hover/dd:rotate-180 opacity-50">
          <path d="M2 3.5L5 6.5L8 3.5" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" />
        </svg>
      </button>

      <div className="absolute top-full left-0 h-4 w-[200%] -left-[20%]" />
      <div className="invisible opacity-0 group-hover/dd:visible group-hover/dd:opacity-100 absolute top-full left-0 z-[100] min-w-[190px] pt-1 spring-transition transition-all duration-300">
        <div className="glass-surface rounded-xl p-1.5 shadow-[0_20px_60px_rgba(0,0,0,0.6)]">
          {items.map((item) => {
            const active = pathname.startsWith(item.href) && item.href !== "/";
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`block text-[12px] font-medium px-3 py-2 rounded-lg spring-transition transition-all duration-200 ${
                  active
                    ? "bg-emerald-500/10 text-emerald-400"
                    : "text-zinc-400 hover:text-white hover:bg-[rgba(255,255,255,0.04)]"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* Layout */

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [user, loading, router]);

  const handleLogout = async () => { await logout(); router.push("/login"); };

  if (loading) {
    return (
      <div className="flex h-screen flex-col items-center justify-center" style={{ background: "var(--db-bg)" }}>
        <Logo size={56} />
        <div className="mt-4 h-1 w-32 overflow-hidden rounded-full bg-zinc-900">
          <div className="h-full animate-pulse rounded-full bg-emerald-500" style={{ width: "60%" }} />
        </div>
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="flex h-screen flex-col overflow-hidden" style={{ background: "var(--db-bg)", color: "#fafafa" }}>
      {/* Background effects */}
      <div className="fixed inset-0 gradient-mesh pointer-events-none" />
      <div className="fixed inset-0 noise-overlay pointer-events-none" />

      {/* Top nav */}
      <nav className="relative z-20 flex h-12 items-center glass-surface border-b border-[rgba(255,255,255,0.04)] px-4 shrink-0">
        <Link href="/" className="flex items-center gap-2.5 mr-5 shrink-0 group">
          <Logo size={26} />
          <div className="hidden sm:flex items-baseline gap-2">
            <span className="text-[14px] font-bold text-white tracking-tight group-hover:text-emerald-400 spring-transition transition-colors duration-300"
              style={{ fontFamily: "var(--font-geist-heading), sans-serif" }}>
              StockPilot
            </span>
            <span className="text-[8px] font-mono font-semibold text-zinc-700 tracking-[0.15em]">QUANT</span>
          </div>
        </Link>

        <div className="w-px h-5 bg-[rgba(255,255,255,0.06)] mr-3 hidden sm:block" />

        {/* Left: direct links */}
        <div className="flex items-center gap-0.5">
          {directLinks.map((item) => {
            const isActive = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link key={item.href} href={item.href}
                className={`text-[12px] font-medium px-3 py-1.5 rounded-lg spring-transition transition-all duration-300 whitespace-nowrap ${
                  isActive
                    ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/15"
                    : "text-zinc-500 hover:text-zinc-200 hover:bg-[rgba(255,255,255,0.04)]"
                }`}
              >
                {item.label}
              </Link>
            );
          })}

          <div className="w-px h-4 bg-[rgba(255,255,255,0.04)] mx-1" />

          {/* Dropdown menus */}
          {dropdowns.map((dd) => (
            <NavDropdown key={dd.label} label={dd.label} items={dd.items} pathname={pathname} />
          ))}

          <div className="w-px h-4 bg-[rgba(255,255,255,0.04)] mx-1" />

          {/* Right links */}
          {rightLinks.map((item) => {
            const isActive = pathname.startsWith(item.href);
            return (
              <Link key={item.href} href={item.href}
                className={`text-[12px] font-medium px-3 py-1.5 rounded-lg spring-transition transition-all duration-300 whitespace-nowrap ${
                  isActive
                    ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/15"
                    : "text-zinc-500 hover:text-zinc-200 hover:bg-[rgba(255,255,255,0.04)]"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </div>

        <div className="flex-1" />

        <div className="flex items-center gap-3 shrink-0">
          {/* LIVE indicator */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-emerald-500/20 bg-emerald-500/5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.6)] animate-pulse" />
            <span className="text-[9px] font-bold text-emerald-400 tracking-[0.15em]">LIVE</span>
          </div>

          {/* Avatar */}
          <Link href="/profile" className="w-7 h-7 rounded-full bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center text-[10px] font-bold text-black shadow-[0_0_16px_rgba(16,185,129,0.2)]">
            {user.name?.charAt(0) || user.email.charAt(0).toUpperCase()}
          </Link>
          <button onClick={handleLogout} className="text-[11px] text-zinc-600 hover:text-zinc-300 spring-transition transition-colors hidden sm:block">
            Sign Out
          </button>
        </div>
      </nav>

      {/* Market ticker */}
      <div className="relative z-10 h-7 border-b border-[rgba(255,255,255,0.04)] shrink-0 flex items-center overflow-hidden px-2" style={{ background: "rgba(5,5,8,0.6)" }}>
        <MarketTicker />
      </div>

      {/* Content */}
      <main className="relative z-10 flex-1 overflow-y-auto p-3 md:p-4 scrollbar-thin">
        {children}
      </main>

      {/* PWA Install Prompt */}
      <InstallPrompt />
    </div>
  );
}
