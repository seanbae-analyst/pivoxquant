"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import { useState } from "react";

interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
}

const sections: { title: string; items: NavItem[] }[] = [
  {
    title: "Portfolio",
    items: [
      { label: "Dashboard", href: "/", icon: <IconChart /> },
      { label: "Alerts", href: "/alerts", icon: <IconBell /> },
      { label: "Trade History", href: "/trades", icon: <IconList /> },
    ],
  },
  {
    title: "Market",
    items: [
      { label: "Market", href: "/market", icon: <IconGlobe /> },
      { label: "Morning Brief", href: "/morning", icon: <IconNews /> },
      { label: "Watchlist", href: "/watchlist", icon: <IconStar /> },
    ],
  },
  {
    title: "Trading",
    items: [
      { label: "Auto Trade", href: "/autotrade", icon: <IconBot /> },
    ],
  },
  {
    title: "Learn",
    items: [
      { label: "Glossary", href: "/glossary", icon: <IconBook /> },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sticky top-14 hidden h-[calc(100vh-3.5rem)] w-[220px] shrink-0 overflow-y-auto border-r border-white/[.04] bg-[#080d14] px-3 py-5 md:block">
      {sections.map((section, si) => (
        <div key={section.title} className={cn("mb-5", si > 0 && "mt-2")}>
          <p className="mb-2 px-3 font-mono text-[9px] font-semibold uppercase tracking-[2px] text-muted-foreground/40">
            {section.title}
          </p>
          <div className="space-y-0.5">
            {section.items.map((item) => {
              const active =
                item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
              return (
                <Link key={item.href} href={item.href}>
                  <motion.div
                    className={cn(
                      "group relative flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] transition-all",
                      active
                        ? "text-white"
                        : "text-muted-foreground hover:text-foreground",
                    )}
                    whileHover={{ x: 2 }}
                    whileTap={{ scale: 0.98 }}
                  >
                    {active && (
                      <motion.div
                        className="absolute inset-0 rounded-lg bg-gradient-to-r from-primary/15 to-transparent"
                        layoutId="sidebar-active"
                        transition={{ type: "spring", duration: 0.4 }}
                      />
                    )}
                    {active && (
                      <motion.div
                        className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-primary"
                        layoutId="sidebar-indicator"
                        transition={{ type: "spring", duration: 0.4 }}
                      />
                    )}
                    <span className={cn(
                      "relative z-10 transition-colors",
                      active ? "text-primary" : "text-muted-foreground/60 group-hover:text-muted-foreground",
                    )}>
                      {item.icon}
                    </span>
                    <span className="relative z-10">{item.label}</span>
                  </motion.div>
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </aside>
  );
}

/* ── Mobile Bottom Nav ── */
export function MobileNav() {
  const pathname = usePathname();
  const items = [
    { label: "Home", href: "/", icon: <IconChart /> },
    { label: "Market", href: "/market", icon: <IconGlobe /> },
    { label: "Trade", href: "/autotrade", icon: <IconBot /> },
    { label: "Alerts", href: "/alerts", icon: <IconBell /> },
    { label: "More", href: "/morning", icon: <IconMore /> },
  ];

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 flex h-14 items-center justify-around border-t border-white/[.06] bg-[#060910]/95 backdrop-blur-xl md:hidden">
      {items.map((item) => {
        const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
        return (
          <Link key={item.href} href={item.href} className="flex flex-col items-center gap-0.5">
            <span className={active ? "text-primary" : "text-muted-foreground/50"}>
              {item.icon}
            </span>
            <span className={cn(
              "text-[9px] font-medium",
              active ? "text-primary" : "text-muted-foreground/40",
            )}>
              {item.label}
            </span>
          </Link>
        );
      })}
    </nav>
  );
}

/* ── Mini SVG Icons (no external dep needed) ── */
function IconChart() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 12 L5 8 L8 10 L11 5 L14 3" />
      <path d="M2 14 L14 14" />
    </svg>
  );
}
function IconBell() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 13a2 2 0 0 0 4 0" /><path d="M4 6a4 4 0 0 1 8 0c0 4 2 5 2 5H2s2-1 2-5" />
    </svg>
  );
}
function IconList() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <path d="M5 4H14M5 8H14M5 12H14M2 4h0M2 8h0M2 12h0" />
    </svg>
  );
}
function IconGlobe() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <circle cx="8" cy="8" r="6" /><path d="M2 8h12M8 2a10 10 0 0 1 0 12M8 2a10 10 0 0 0 0 12" />
    </svg>
  );
}
function IconNews() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="2" width="12" height="12" rx="1" /><path d="M5 5h6M5 8h4M5 11h5" />
    </svg>
  );
}
function IconStar() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 2l1.8 3.6L14 6.4l-3 2.9.7 4.1L8 11.4l-3.7 2 .7-4.1-3-2.9 4.2-.8z" />
    </svg>
  );
}
function IconBot() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="5" width="10" height="8" rx="2" /><circle cx="6" cy="9" r="1" fill="currentColor" /><circle cx="10" cy="9" r="1" fill="currentColor" /><path d="M8 2v3M5 2h6" />
    </svg>
  );
}
function IconBook() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 3h4.5a2 2 0 0 1 2 2v9a1.5 1.5 0 0 0-1.5-1.5H2zM14 3H9.5a2 2 0 0 0-2 2v9a1.5 1.5 0 0 1 1.5-1.5H14z" />
    </svg>
  );
}
function IconMore() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
      <circle cx="4" cy="8" r="1.5" /><circle cx="8" cy="8" r="1.5" /><circle cx="12" cy="8" r="1.5" />
    </svg>
  );
}
