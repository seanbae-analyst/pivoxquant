"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Logo } from "@/components/ui/logo";
import type { User } from "@/lib/auth";

const directLinks = [
  { label: "Portfolio", href: "/" },
  { label: "Market", href: "/market" },
  { label: "Trading", href: "/autotrade" },
  { label: "Alerts", href: "/alerts" },
];

const dropdowns = [
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
  { label: "Trades", href: "/trades" },
  { label: "Watchlist", href: "/watchlist" },
];

function NavDrop({ label, items, pathname }: { label: string; items: { label: string; href: string }[]; pathname: string }) {
  const isActive = items.some(i => pathname.startsWith(i.href) && i.href !== "/");
  return (
    <div className="group/dd relative">
      <button className={`text-[12px] font-medium px-3 py-1.5 rounded-lg spring-transition transition-all duration-300 whitespace-nowrap flex items-center gap-1 ${
        isActive
          ? "bg-emerald-50 text-emerald-600 border border-emerald-200"
          : "text-slate-500 hover:text-slate-900 hover:bg-slate-100"
      }`}>
        {label}
        <svg width="8" height="8" viewBox="0 0 10 10" className="spring-transition transition-transform duration-300 group-hover/dd:rotate-180 opacity-50">
          <path d="M2 3.5L5 6.5L8 3.5" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" />
        </svg>
      </button>
      <div className="absolute top-full left-0 h-4 w-[200%] -left-[20%]" />
      <div className="invisible opacity-0 group-hover/dd:visible group-hover/dd:opacity-100 absolute top-full left-0 z-[100] min-w-[190px] pt-1 spring-transition transition-all duration-300">
        <div className="bg-white rounded-xl p-1.5 shadow-[0_20px_60px_rgba(0,0,0,0.1)] border border-slate-200">
          {items.map((item) => {
            const active = pathname.startsWith(item.href) && item.href !== "/";
            return (
              <Link key={item.href} href={item.href}
                className={`block text-[12px] font-medium px-3 py-2 rounded-lg spring-transition transition-all duration-200 ${
                  active
                    ? "bg-emerald-50 text-emerald-600"
                    : "text-slate-500 hover:text-slate-900 hover:bg-slate-100"
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

interface Props {
  user: User;
  onLogout: () => void;
  onTogglePanel: () => void;
  isPanelOpen: boolean;
}

export function TerminalNav({ user, onLogout, onTogglePanel, isPanelOpen }: Props) {
  const pathname = usePathname();

  return (
    <nav className="flex h-12 items-center bg-white border-b border-slate-200 px-4 shrink-0">
      <Link href="/" className="flex items-center gap-2.5 mr-5 shrink-0 group">
        <Logo size={26} />
        <div className="hidden sm:flex items-baseline gap-2">
          <span className="text-[14px] font-bold text-slate-900 tracking-tight group-hover:text-emerald-600 spring-transition transition-colors duration-300"
            style={{ fontFamily: "var(--font-geist-heading), sans-serif" }}>
            StockPilot
          </span>
          <span className="text-[8px] font-mono font-semibold text-slate-400 tracking-[0.15em]">QUANT</span>
        </div>
      </Link>

      {/* Separator */}
      <div className="w-px h-5 bg-slate-200 mr-3 hidden sm:block" />

      <div className="flex items-center gap-0.5">
        {directLinks.map((item) => {
          const isActive = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <Link key={item.href} href={item.href}
              className={`text-[12px] font-medium px-3 py-1.5 rounded-lg spring-transition transition-all duration-300 whitespace-nowrap ${
                isActive
                  ? "bg-emerald-50 text-emerald-600 border border-emerald-200"
                  : "text-slate-500 hover:text-slate-900 hover:bg-slate-100"
              }`}
            >
              {item.label}
            </Link>
          );
        })}

        <div className="w-px h-4 bg-slate-200 mx-1" />

        {dropdowns.map((dd) => (
          <NavDrop key={dd.label} label={dd.label} items={dd.items} pathname={pathname} />
        ))}

        <div className="w-px h-4 bg-slate-200 mx-1" />

        {rightLinks.map((item) => {
          const isActive = pathname.startsWith(item.href);
          return (
            <Link key={item.href} href={item.href}
              className={`text-[12px] font-medium px-3 py-1.5 rounded-lg spring-transition transition-all duration-300 whitespace-nowrap ${
                isActive
                  ? "bg-emerald-50 text-emerald-600 border border-emerald-200"
                  : "text-slate-500 hover:text-slate-900 hover:bg-slate-100"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </div>

      <div className="flex-1" />

      <div className="flex items-center gap-3 shrink-0">
        {/* Panel toggle */}
        <button onClick={onTogglePanel}
          className={`hidden md:flex items-center gap-1.5 text-[11px] px-2.5 py-1.5 rounded-lg spring-transition transition-all duration-300 ${
            isPanelOpen
              ? "bg-emerald-50 text-emerald-600 border border-emerald-200"
              : "text-slate-400 hover:text-slate-700 hover:bg-slate-100"
          }`}
          title="Toggle panel"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <rect x="1" y="1" width="12" height="12" rx="2.5" stroke="currentColor" strokeWidth="1.2" />
            <line x1="9" y1="1" x2="9" y2="13" stroke="currentColor" strokeWidth="1.2" />
          </svg>
        </button>

        {/* LIVE indicator */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-emerald-200 bg-emerald-50">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.4)] animate-pulse" />
          <span className="text-[9px] font-bold text-emerald-600 tracking-[0.15em]">LIVE</span>
        </div>

        {/* Avatar */}
        <Link href="/profile" className="w-7 h-7 rounded-full bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center text-[10px] font-bold text-black shadow-[0_0_16px_rgba(16,185,129,0.2)]">
          {user.name?.charAt(0) || user.email.charAt(0).toUpperCase()}
        </Link>
        <button onClick={onLogout} className="text-[11px] text-slate-400 hover:text-slate-700 spring-transition transition-colors duration-300 hidden sm:block">
          Sign Out
        </button>
      </div>
    </nav>
  );
}
