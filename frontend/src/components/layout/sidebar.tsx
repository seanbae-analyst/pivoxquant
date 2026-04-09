"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
}

const sections: { title: string; items: NavItem[] }[] = [
  {
    title: "Portfolio",
    items: [
      { label: "Dashboard", href: "/dashboard", icon: <IconChart /> },
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
    <aside className="sticky top-14 hidden h-[calc(100vh-3.5rem)] w-[220px] shrink-0 overflow-y-auto border-r border-border bg-white px-3 py-5 md:block">
      {sections.map((section, si) => (
        <div key={section.title} className={cn("mb-4", si > 0 && "mt-1")}>
          {/* Section divider */}
          {si > 0 && (
            <div className="mb-3 h-px bg-gradient-to-r from-transparent via-border/60 to-transparent" />
          )}
          <p className="mb-2 px-3 font-mono text-[9px] font-semibold uppercase tracking-[2px] text-muted-foreground/30">
            {section.title}
          </p>
          <div className="space-y-0.5">
            {section.items.map((item) => {
              const active =
                item.href === "/dashboard" ? pathname === "/dashboard" : pathname.startsWith(item.href);
              return (
                <Link key={item.href} href={item.href}>
                  <motion.div
                    className={cn(
                      "group relative flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] transition-all",
                      active
                        ? "text-foreground font-semibold"
                        : "text-muted-foreground hover:text-foreground",
                    )}
                    whileHover={{ x: 2 }}
                    whileTap={{ scale: 0.98 }}
                  >
                    {active && (
                      <motion.div
                        className="absolute inset-0 rounded-lg bg-gradient-to-r from-primary/12 to-transparent"
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
                      active ? "text-primary" : "text-muted-foreground/40 group-hover:text-muted-foreground/70",
                    )}>
                      {item.icon}
                    </span>
                    <span className="relative z-10 font-medium">{item.label}</span>
                  </motion.div>
                </Link>
              );
            })}
          </div>
        </div>
      ))}

      {/* Bottom branding */}
      <div className="mt-auto pt-6">
        <div className="h-px bg-gradient-to-r from-transparent via-border/60 to-transparent" />
        <div className="px-3 pt-4">
          <p className="font-mono text-[8px] tracking-[1.5px] text-muted-foreground/20">
            QUANT ENGINE v4
          </p>
          <p className="mt-0.5 font-mono text-[8px] tracking-wider text-muted-foreground/15">
            15+ INDICATORS
          </p>
        </div>
      </div>
    </aside>
  );
}

/* ── Mobile Bottom Nav ── */
export function MobileNav() {
  const pathname = usePathname();
  const items = [
    { label: "Home", href: "/dashboard", icon: <IconChart /> },
    { label: "Market", href: "/market", icon: <IconGlobe /> },
    { label: "Trade", href: "/autotrade", icon: <IconBot /> },
    { label: "Alerts", href: "/alerts", icon: <IconBell /> },
    { label: "More", href: "/morning", icon: <IconMore /> },
  ];

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 flex h-14 items-center justify-around border-t border-border bg-white/90 backdrop-blur-xl md:hidden">
      {items.map((item) => {
        const active = item.href === "/dashboard" ? pathname === "/dashboard" : pathname.startsWith(item.href);
        return (
          <Link key={item.href} href={item.href} className="flex flex-col items-center gap-0.5">
            <span className={active ? "text-primary" : "text-muted-foreground/40"}>
              {item.icon}
            </span>
            <span className={cn(
              "text-[9px] font-medium",
              active ? "text-primary" : "text-muted-foreground/30",
            )}>
              {item.label}
            </span>
          </Link>
        );
      })}
    </nav>
  );
}

/* ── SVG Icons (18px) ── */
function IconChart() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 14 L5.5 9 L9 11 L12.5 5.5 L16 3.5" />
      <path d="M2 16 L16 16" />
    </svg>
  );
}
function IconBell() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M7 15a2 2 0 0 0 4 0" /><path d="M4.5 7a4.5 4.5 0 0 1 9 0c0 4.5 2 5.5 2 5.5H2.5s2-1 2-5.5" />
    </svg>
  );
}
function IconList() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <path d="M6 4.5H16M6 9H16M6 13.5H16M2.5 4.5h0M2.5 9h0M2.5 13.5h0" />
    </svg>
  );
}
function IconGlobe() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <circle cx="9" cy="9" r="7" /><path d="M2 9h14M9 2a12 12 0 0 1 0 14M9 2a12 12 0 0 0 0 14" />
    </svg>
  );
}
function IconNews() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="2" width="14" height="14" rx="1.5" /><path d="M5.5 5.5h7M5.5 9h5M5.5 12.5h6" />
    </svg>
  );
}
function IconStar() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 2l2 4.2L15.5 7l-3.5 3.3.8 4.7L9 12.8l-3.8 2.2.8-4.7L2.5 7l4.5-.8z" />
    </svg>
  );
}
function IconBot() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="6" width="12" height="9" rx="2" /><circle cx="7" cy="10.5" r="1" fill="currentColor" /><circle cx="11" cy="10.5" r="1" fill="currentColor" /><path d="M9 2.5v3.5M6 2.5h6" />
    </svg>
  );
}
function IconBook() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 3.5h5a2 2 0 0 1 2 2V15a1.5 1.5 0 0 0-1.5-1.5H2zM16 3.5h-5a2 2 0 0 0-2 2V15a1.5 1.5 0 0 1 1.5-1.5H16z" />
    </svg>
  );
}
function IconMore() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="currentColor">
      <circle cx="4.5" cy="9" r="1.5" /><circle cx="9" cy="9" r="1.5" /><circle cx="13.5" cy="9" r="1.5" />
    </svg>
  );
}
